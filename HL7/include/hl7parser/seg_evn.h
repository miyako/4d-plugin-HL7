#ifndef HL7PARSER_SEG_EVN_H
#define HL7PARSER_SEG_EVN_H

/**
* \file seg_evn.h
*
* Event type segment (EVN) accessors for the HL7 parser.
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
* Get the recorded_date (EVN.2) field.
*/
HL7_EXPORT time_t hl7_evn_recorded_date( HL7_Segment *segment );
/**
* Set the recorded_date (EVN.2) field.
*/
HL7_EXPORT int hl7_evn_set_recorded_date( HL7_Segment *segment, HL7_Element *element );
/**
* Set the recorded_date (EVN.2) field as a time_t.
*/
HL7_EXPORT int hl7_evn_set_recorded_date_time( HL7_Segment *segment, const time_t value );
/**
* Get the planned_event_date (EVN.3) field.
*/
HL7_EXPORT time_t hl7_evn_planned_event_date( HL7_Segment *segment );
/**
* Set the planned_event_date (EVN.3) field.
*/
HL7_EXPORT int hl7_evn_set_planned_event_date( HL7_Segment *segment, HL7_Element *element );
/**
* Set the planned_event_date (EVN.3) field as a time_t.
*/
HL7_EXPORT int hl7_evn_set_planned_event_date_time( HL7_Segment *segment, const time_t value );

END_C_DECL()

#endif /* HL7_SEG_EVN_H */
