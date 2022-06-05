#ifndef HL7PARSER_SEG_PV2_H
#define HL7PARSER_SEG_PV2_H

/**
* \file seg_pv2.h
*
* Patient visit - additional information segment (PV2) accessors for the HL7 parser.
*
* \internal
* Copyright (c) 2011 Juan Jose Comellas <juanjo@comellas.org>
*
* \warning DO NOT MODIFY THIS FILE.
*
* Autogenerated by the ./hl7segdef.py script on Mon Jun  6 12:54:47 2011
*/

/* ------------------------------------------------------------------------
   Headers
   ------------------------------------------------------------------------ */

#include <hl7parser/config.h>
#include <hl7parser/element.h>
#include <hl7parser/export.h>
#include <hl7parser/segment.h>

BEGIN_C_DECL()

/* ------------------------------------------------------------------------
   Function prototypes
   ------------------------------------------------------------------------ */

/**
* Get the transfer_reason_id (PV2.4.1) component.
*/
HL7_EXPORT HL7_Element *hl7_pv2_transfer_reason_id( HL7_Segment *segment );
/**
* Set the transfer_reason_id (PV2.4.1) component.
*/
HL7_EXPORT int hl7_pv2_set_transfer_reason_id( HL7_Segment *segment, HL7_Element *element );
/**
* Set the transfer_reason_id (PV2.4.1) component as a string.
*/
HL7_EXPORT int hl7_pv2_set_transfer_reason_id_str( HL7_Segment *segment, const char *value );

END_C_DECL()

#endif /* HL7_SEG_PV2_H */
