//! Bounded HTTP/1.1 loopback client. Remote TLS transport must be supplied by an
//! audited integration; this module refuses remote plaintext and redirects.
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::time::Duration;

#[derive(Debug, PartialEq, Eq)]
pub enum Error { Configuration, Transport, Protocol, TooLarge, Http(u16) }

pub struct Client {
    address: SocketAddr,
    participant: String,
    token: String,
    timeout: Duration,
    max_response: usize,
}

fn credential(value: &str, maximum: usize) -> bool {
    !value.is_empty() && value.len() <= maximum &&
    value.bytes().all(|b| (33..=126).contains(&b))
}

impl Client {
    pub fn loopback(address: SocketAddr, participant: &str, token: &str,
                    timeout: Duration, max_response: usize) -> Result<Self, Error> {
        if !address.ip().is_loopback() || address.port() == 0 ||
           !credential(participant, 128) || !credential(token, 4096) ||
           timeout.is_zero() || timeout > Duration::from_secs(60) ||
           max_response == 0 || max_response > 1_048_576 {
            return Err(Error::Configuration);
        }
        Ok(Self { address, participant: participant.into(), token: token.into(), timeout, max_response })
    }

    /// Returns bounded UTF-8 JSON bytes for the versioned scientific API.
    /// JSON interpretation and scientific result verification remain caller duties.
    pub fn request(&self, method: &str, path: &str, json: Option<&str>) -> Result<String, Error> {
        if !["GET", "POST"].contains(&method) || !path.starts_with('/') ||
           path.len() > 1024 || !path.bytes().all(|b| b.is_ascii_alphanumeric() || b"/-_".contains(&b)) {
            return Err(Error::Configuration);
        }
        let body = json.unwrap_or("");
        if body.len() > 65536 || (method == "GET" && !body.is_empty()) { return Err(Error::TooLarge); }
        let mut stream = TcpStream::connect_timeout(&self.address, self.timeout).map_err(|_|Error::Transport)?;
        stream.set_read_timeout(Some(self.timeout)).map_err(|_|Error::Transport)?;
        stream.set_write_timeout(Some(self.timeout)).map_err(|_|Error::Transport)?;
        let request = format!("{} {} HTTP/1.1\r\nHost: {}\r\nAuthorization: Bearer {}\r\nX-Nabla-Participant: {}\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: {}\r\n\r\n{}",
                              method,path,self.address,self.token,self.participant,body.len(),body);
        stream.write_all(request.as_bytes()).map_err(|_|Error::Transport)?;
        let mut bytes=Vec::new();
        stream.take((self.max_response+16385) as u64).read_to_end(&mut bytes).map_err(|_|Error::Transport)?;
        decode_response(&bytes,self.max_response)
    }
}

pub fn decode_response(bytes: &[u8], maximum: usize) -> Result<String, Error> {
    let boundary=bytes.windows(4).position(|w|w==b"\r\n\r\n").ok_or(Error::Protocol)?;
    if boundary>16384 {return Err(Error::TooLarge)}
    let headers=std::str::from_utf8(&bytes[..boundary]).map_err(|_|Error::Protocol)?;
    let mut lines=headers.split("\r\n");
    let status=lines.next().ok_or(Error::Protocol)?;
    let mut pieces=status.splitn(3,' ');
    if !["HTTP/1.1","HTTP/1.0"].contains(&pieces.next().unwrap_or("")) {return Err(Error::Protocol)}
    let code=pieces.next().ok_or(Error::Protocol)?.parse::<u16>().map_err(|_|Error::Protocol)?;
    if code!=200 {return Err(Error::Http(code))}
    let mut length=None;let mut content_type=false;
    for line in lines {
        let (name,value)=line.split_once(':').ok_or(Error::Protocol)?;
        match name.to_ascii_lowercase().as_str() {
            "content-length" => {
                if length.is_some() {return Err(Error::Protocol)}
                length=Some(value.trim().parse::<usize>().map_err(|_|Error::Protocol)?);
            },
            "content-type" => {
                if content_type || value.trim()!="application/json" {return Err(Error::Protocol)}
                content_type=true;
            },
            "transfer-encoding" => return Err(Error::Protocol),
            _ => (),
        }
    }
    let body=&bytes[boundary+4..];
    if body.len()>maximum {return Err(Error::TooLarge)}
    if !content_type || length!=Some(body.len()) {return Err(Error::Protocol)}
    Ok(std::str::from_utf8(body).map_err(|_|Error::Protocol)?.into())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::IpAddr;
    #[test]
    fn refuses_remote_and_header_injection() {
        let remote=SocketAddr::new("192.0.2.1".parse::<IpAddr>().unwrap(),80);
        assert!(matches!(Client::loopback(remote,"p","t",Duration::from_secs(1),100),Err(Error::Configuration)));
        let local="127.0.0.1:80".parse().unwrap();
        assert!(matches!(Client::loopback(local,"p\r\nx","t",Duration::from_secs(1),100),Err(Error::Configuration)));
    }
    #[test]
    fn strict_framing() {
        assert_eq!(decode_response(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}",100),Ok("{}".into()));
        assert_eq!(decode_response(b"HTTP/1.1 302 Found\r\n\r\n",100),Err(Error::Http(302)));
        assert!(decode_response(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 3\r\n\r\n{}",100).is_err());
    }
}
