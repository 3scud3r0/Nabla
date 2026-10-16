"""Actual independent process conformance; unavailable compilers are explicit skips."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[2]
VECTORS=json.loads((ROOT/'protocol/fixtures/cross-language/rational-v1.json').read_text())


def run(command,**kwargs):
    return subprocess.run(command,capture_output=True,text=True,timeout=30,**kwargs)


def test_python_normative_vectors():
    spec=importlib.util.spec_from_file_location('nabla_sdk_rational',ROOT/'sdk/python/rational.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for value in VECTORS['valid']:
        assert module.parse_fraction(value)[1]>0
    for value in VECTORS['invalid']:
        with pytest.raises(ValueError):module.parse_fraction(value)


@pytest.mark.parametrize('language',['c','cpp'])
def test_c_cpp_normative_vectors(tmp_path,language):
    compiler=shutil.which('cc' if language=='c' else 'c++')
    if not compiler:pytest.skip('C/C++ compiler unavailable')
    source=tmp_path/('main.c' if language=='c' else 'main.cpp')
    if language=='c':
        source.write_text('#include "nabla_fraction.h"\nint main(int n,char**v){nm_fraction f;return n==2&&nm_parse_fraction(v[1],&f)==0?0:1;}\n')
    else:
        source.write_text('#include "nabla_fraction.hpp"\nint main(int n,char**v){return n==2&&nabla::parse_fraction(v[1]).has_value()?0:1;}\n')
    binary=tmp_path/'reader'
    command=[compiler,str(source),str(ROOT/'sdk/c/nabla_fraction.c'),'-I'+str(ROOT/'sdk'/language),'-o',str(binary)]
    result=run(command)
    assert result.returncode==0,result.stderr
    for value in VECTORS['valid']:
        assert run([str(binary),value]).returncode==0,repr(value)
    for value in VECTORS['invalid']:
        assert run([str(binary),value]).returncode!=0,repr(value)


def test_typescript_normative_vectors(tmp_path):
    node=shutil.which('node')
    if not node:pytest.skip('Node unavailable')
    script=tmp_path/'check.mjs'
    script.write_text('import {parseFraction} from '+json.dumps((ROOT/'sdk/typescript/rational.ts').as_uri())+';\n'+
                      'const v='+json.dumps(VECTORS)+'; for(const x of v.valid)parseFraction(x);'+
                      'for(const x of v.invalid){let failed=false;try{parseFraction(x)}catch{failed=true}if(!failed)throw Error(x)}')
    result=run([node,'--experimental-strip-types',str(script)])
    assert result.returncode==0,result.stderr


@pytest.fixture(scope='module')
def rust_reader(tmp_path_factory):
    cargo=shutil.which('cargo')
    rustc=shutil.which('rustc')
    if not cargo or not rustc:pytest.skip('Rust toolchain unavailable; Rust interop not executed')
    temporary=tmp_path_factory.mktemp('rust-interop')
    target=temporary/'target'
    result=run([cargo,'test','--offline','--manifest-path',str(ROOT/'sdk/rust/Cargo.toml'),'--target-dir',str(target)])
    assert result.returncode==0,result.stderr
    result=run([cargo,'build','--offline','--manifest-path',str(ROOT/'sdk/rust/Cargo.toml'),'--target-dir',str(target)])
    assert result.returncode==0,result.stderr
    source=temporary/'reader.rs'
    source.write_text(r'''use nablamath_fraction::{parse_fraction,client::Client};
use std::time::Duration;
fn main(){
 let args:Vec<String>=std::env::args().collect();
 if args.len()==3 && args[1]=="fraction" {
   match parse_fraction(&args[2]) {Some(v)=>println!("{}/{}",v.numerator,v.denominator),None=>std::process::exit(1)}
 } else if args.len()==3 && args[1]=="http" {
   let client=Client::loopback(args[2].parse().unwrap(),"participant","test-token",Duration::from_secs(2),1024).unwrap();
   match client.request("GET","/status",None) {Ok(v)=>println!("{}",v),Err(_)=>std::process::exit(2)}
 } else {std::process::exit(3)}
}
''')
    binary=temporary/'reader'
    result=run([rustc,'--edition=2021',str(source),'--extern','nablamath_fraction='+str(target/'debug/libnablamath_fraction.rlib'),'-L',str(target/'debug/deps'),'-o',str(binary)])
    assert result.returncode==0,result.stderr
    return binary


def test_rust_normative_vectors_when_toolchain_available(rust_reader):
    for value in VECTORS['valid']:
        result=run([str(rust_reader),'fraction',value])
        assert result.returncode==0,(value,result.stderr)
        from fractions import Fraction
        assert Fraction(result.stdout.strip())==Fraction(value)
    for value in VECTORS['invalid']:
        assert run([str(rust_reader),'fraction',value]).returncode==1,repr(value)


def test_rust_authenticated_loopback_http_client(rust_reader):
    from http.server import BaseHTTPRequestHandler,HTTPServer
    from threading import Thread
    observed=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            observed.append((self.path,self.headers.get('Authorization'),self.headers.get('X-Nabla-Participant')))
            body=b'{"status":"ready"}'
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    server=HTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        result=run([str(rust_reader),'http','127.0.0.1:'+str(server.server_port)])
        assert result.returncode==0,result.stderr
        assert json.loads(result.stdout)=={'status':'ready'}
        assert observed==[('/status','Bearer test-token','participant')]
    finally:
        server.shutdown();thread.join(timeout=3);server.server_close()
