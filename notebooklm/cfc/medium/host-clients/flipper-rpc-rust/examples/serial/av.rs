use flipper_rpc::{
    error::Result,
    rpc::req::Request,
    transport::{
        Transport,
        serial::{list_flipper_ports, rpc::SerialRpcTransport},
    },
};

fn main() -> Result<()> {
    let ports = list_flipper_ports()?;

    let port = &ports[0].port_name;

    let mut cli = SerialRpcTransport::new(port)?;

    cli.send_and_receive(Request::PlayAvAlert)?; // wee-woo

    Ok(())
}
