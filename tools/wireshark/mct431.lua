-- We decode the custom TCP inspection stream, including TCP reassembly.
local p = Proto("mct431", "MCT431 inspection protocol")
local kinds = {[1]="COMMAND",[2]="DELIVERED",[3]="ACCEPTED",[4]="COMPLETED",[5]="REJECTED",[6]="HELLO",[7]="PING"}
local ops = {[0]="NONE",[1]="BIND",[2]="CONFIG",[3]="PRODUCE",[4]="INSPECT"}
local f = {
  length=ProtoField.uint16("mct431.length","Length",base.DEC),
  version=ProtoField.uint8("mct431.version","Version",base.DEC),
  kind=ProtoField.uint8("mct431.kind","Kind",base.DEC,kinds),
  op=ProtoField.uint8("mct431.op","Operation",base.DEC,ops),
  station=ProtoField.uint8("mct431.station","Station",base.DEC),
  session=ProtoField.uint64("mct431.session","Session",base.HEX),
  command=ProtoField.uint32("mct431.command_id","Command ID",base.DEC),
  part=ProtoField.uint32("mct431.part_id","Part ID",base.DEC),
  arg0=ProtoField.uint32("mct431.arg0","Duration / result / error",base.DEC),
  arg1=ProtoField.uint32("mct431.arg1","N / last ID",base.DEC),
  arg2=ProtoField.uint32("mct431.arg2","K",base.DEC),
  boot=ProtoField.uint32("mct431.boot","Boot nonce",base.HEX)
}
p.fields=f
function p.dissector(buffer, info, tree)
  local offset=0
  while offset<buffer:len() do
    local remaining=buffer:len()-offset
    if remaining<2 then info.desegment_offset=offset;info.desegment_len=2-remaining;return end
    local length=buffer(offset,2):uint()
    if length~=36 then return end
    if remaining<length+2 then info.desegment_offset=offset;info.desegment_len=length+2-remaining;return end
    local t=tree:add(p,buffer(offset,length+2))
    t:add(f.length,buffer(offset,2));local o=offset+2
    t:add(f.version,buffer(o,1));t:add(f.kind,buffer(o+1,1));t:add(f.op,buffer(o+2,1));t:add(f.station,buffer(o+3,1))
    t:add(f.session,buffer(o+4,8));t:add(f.command,buffer(o+12,4));t:add(f.part,buffer(o+16,4))
    t:add(f.arg0,buffer(o+20,4));t:add(f.arg1,buffer(o+24,4));t:add(f.arg2,buffer(o+28,4));t:add(f.boot,buffer(o+32,4))
    info.cols.protocol="MCT431"
    info.cols.info=(kinds[buffer(o+1,1):uint()] or "UNKNOWN").." "..(ops[buffer(o+2,1):uint()] or "UNKNOWN")..
      " cmd="..buffer(o+12,4):uint().." part="..buffer(o+16,4):uint()
    offset=offset+length+2
  end
end
DissectorTable.get("tcp.port"):add(9000,p)
