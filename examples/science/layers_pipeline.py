"""Run the bounded CPU laboratory -> GLB -> MP4 -> signed Typst PDF workflow.

Install nablamath[torch,formal,federation,publishing,animation] and Manim's
system dependencies. Use a NEW output directory; private keys stay in memory.
Run this file as a program because the SMT verifier uses spawned processes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from importlib.resources import files
from pathlib import Path

from nablamath.ai.sandbox_verifier import AIVerifier, VerificationStatus
from nablamath.artifacts.bundle import create_bundle, save_bundle
from nablamath.backends.cuda_dispatcher import CudaDispatcher, available_backends
from nablamath.calc import CalculationSession
from nablamath.calc.receipt import receipt
from nablamath.compat.pytorch_bridge import TorchTrace
from nablamath.federation.crypto_registry import (
    CryptoRegistry, generate_key, public_key_hex, sign,
)
from nablamath.graphics.manim_animator import ManimAnimator
from nablamath.graphics.webgl_exporter import WebGLExporter
from nablamath.publishing import TypstCompiler, verify_publication


def run(destination: Path, *, video=True, cuda=False):
    import torch

    destination.mkdir(parents=True, exist_ok=False)
    records = []
    verifier = AIVerifier()
    supported = verifier.verify('x*x >= 0')
    refuted = verifier.verify('x+1 = x')
    if supported.status != VerificationStatus.PROVEN or refuted.status != VerificationStatus.COUNTEREXAMPLE_FOUND:
        raise RuntimeError('Expected SMT positive and negative controls did not pass')
    records.append(receipt('demo.conjectures', {'goals':['x*x >= 0','x+1 = x']},
                           {'supported':supported.to_data(), 'refuted':refuted.to_data()}, backend='z3'))

    dispatcher = CudaDispatcher(backend='torch', require_cuda=cuda)
    with CalculationSession(background_receipts=True, receipt_sink=records.append) as session:
        session.execute('spectral', kind='fft', values=[1,0,0,0]).to_data()
        session.execute('complex_analysis', kind='mobius', points=[[1,1]],
                        coefficients=[[1,0],[0,0],[0,0],[1,0]]).to_data()
        session.execute('differential_geometry', metric=[[1,0],[0,1]]).to_data()
        session.execute('abstract_algebra', kind='primality', n=97).to_data()
        ode = session.execute('ode', model='exponential_decay', initial=[1.], steps=40).to_data()
        fit = session.execute_accelerated('least_squares', dispatcher=dispatcher,
            predictors=[[0],[1],[2]], response=[1,3,5], capture_values=True).to_data()
        native = torch.arange(4., device=dispatcher.platform, requires_grad=True).reshape(2,2)
        with TorchTrace(session, batch_size=128) as trace:
            (native @ native.T).sum().backward()

    # A ribbon with heights taken directly from the audited decay trajectory.
    trajectory = ode['result']['trajectory']
    exporter = WebGLExporter()
    vertices, faces = exporter.heightfield([[state[0], state[0]] for _,state in trajectory],
                                           spacing=(.1, 1/(len(trajectory)-1)))
    mesh = exporter.export_glb(vertices, faces, destination/'decay.glb', audit_receipt=ode)
    exporter.inspect_glb(mesh)
    animator = ManimAnimator(duration=1)
    animator.export_script(ode, destination/'decay_scene.py')
    if video:
        rendered = animator.render(ode, destination/'decay.mp4')
        records.append(rendered['receipt'])

    points = ' '.join(f'{60+410*t:.4f},{250-200*state[0]:.4f}' for t,state in trajectory)
    ticks = ''.join(f'<path d="M{60+410*t} 50 V250 M60 {250-200*t} H470" stroke="#e3e9ec"/>'
                    f'<text x="{60+410*t}" y="273" text-anchor="middle">{t:g}</text>'
                    f'<text x="48" y="{255-200*t}" text-anchor="end">{t:g}</text>' for t in (0,.25,.5,.75,1))
    (destination/'decay.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="500" height="310">'
        '<rect width="500" height="310" fill="white"/>'
        '<g font-family="DejaVu Sans" font-size="16" fill="#526471">'
        '<text x="60" y="24" font-weight="bold" fill="#172b3a">Exponential decay · RK4</text>'
        +ticks+'<path d="M60 45 V250 H475" stroke="#526471" fill="none"/>'
        '<text x="265" y="303" text-anchor="middle">t (normalized)</text>'
        '<text x="12" y="150" transform="rotate(-90 12 150)" text-anchor="middle">u(t)</text></g>'
        f'<polyline points="{points}" fill="none" stroke="#117879" stroke-width="3"/>'
        '</svg>', encoding='utf-8')
    bundle = create_bundle(records, datasets={'glb_sha256':hashlib.sha256(mesh.read_bytes()).hexdigest()})
    save_bundle(bundle, destination/'experiment.json')
    key = generate_key()
    signature = sign(bundle, key, signer='local-demo-laboratory')
    trust = CryptoRegistry()
    trust.pin(signature['signer'], public_key_hex(key))
    (destination/'signature.json').write_text(json.dumps(signature, indent=2)+'\n')
    template = destination/'living.typ'
    template.write_text(files('nablamath.publishing').joinpath('templates/living_paper.typ').read_text(),encoding='utf-8')
    ode_index = next(i for i,r in enumerate(records) if r['content_id'] == ode['content_id'])
    fit_index = next(i for i,r in enumerate(records) if r['content_id'] == fit['content_id'])
    paper = TypstCompiler(trust=trust, require_signature=True).compile(
        bundle, destination/'living.pdf', template=template,
        variables={'final_state':f'/receipts/{ode_index}/result/final',
                   'least_squares_coefficients':f'/receipts/{fit_index}/result/coefficients'},
        figures=[{'path':'decay.svg','caption':'Samples from the audited RK4 trajectory'}],
        asset_root=destination, signature=signature,
        title='Exponential decay: an auditable numerical experiment',
        authors=['Nabla · reproducible computational demonstration'],
        abstract='A synthetic exponential-decay model is integrated with RK4. '
                 'A separate linear regression checks a known affine law. '
                 'Recorded tensors, mathematical results, figure and publication are linked by audit receipts. '
                 'The calculation demonstrates software behavior and does not validate a physical hypothesis.')
    if not verify_publication(paper.pdf, trust=trust, require_signature=True):
        raise RuntimeError('Publication verification failed')
    summary = {'available_backends':available_backends(), 'selected_backend':dispatcher.backend,
               'selected_platform':dispatcher.platform, 'receipts':len(records),
               'traced_operations':trace.operation_count, 'experiment_hash':bundle['content_id'],
               'pdf_verified':True, 'mp4_rendered':video, 'glb_inspected':True,
               'limits':'Finite synthetic CPU/CUDA profile; no universal mathematics or production certification.'}
    (destination/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--skip-video', action='store_true', help='Export the scene without rendering MP4')
    parser.add_argument('--cuda', action='store_true', help='Require an actual NVIDIA device')
    args = parser.parse_args()
    print(json.dumps(run(args.destination, video=not args.skip_video, cuda=args.cuda), indent=2))
