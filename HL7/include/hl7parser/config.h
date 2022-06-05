#ifndef HL7PARSER_CONFIG_H
#define HL7PARSER_CONFIG_H

/**
* \file config.h
*
* Generic configuration directives and macros used by the HL7 parser.
*
* \internal
* Copyright (c) 2003-2013 Juan Jose Comellas <juanjo@comellas.org>
*/

/* ------------------------------------------------------------------------
   Headers
   ------------------------------------------------------------------------ */

#include <hl7parser/bool.h>
#include <assert.h>


/* ------------------------------------------------------------------------
   Macros
   ------------------------------------------------------------------------ */

/* Macros used when the library is included in a C++ project. */
#ifdef __cplusplus

#   define BEGIN_C_DECL()  extern "C" {
#   define END_C_DECL()    }

#else

#   define BEGIN_C_DECL()
#   define END_C_DECL()

#endif /* __cplusplus */

/**
* \def HL7_ASSERT( p )
* Asserts that the predicate \a p is true; if not it aborts the program
* showing the predicate, file and line number where the assertion failed.
*/
#define HL7_ASSERT( p )     assert( p )

#ifdef __GNUC__
#define HL7_UNUSED __attribute__ ((__unused__))
#else
#define HL7_UNUSED
#endif

#endif /* HL7PARSER_CONFIG_H */
