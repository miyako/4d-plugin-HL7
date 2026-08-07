//%attributes = {}
$msg:=Folder:C1567(fk resources folder:K87:11).file("test.hl7").getText("utf-8")

//$msg:=Folder(fk resources folder).file("duck.hl7").getText("utf-8")

$status:=HL7 Parse($msg)