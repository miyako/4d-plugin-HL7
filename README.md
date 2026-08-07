![version](https://img.shields.io/badge/version-17%2B-3E8B93)
![platform](https://img.shields.io/static/v1?label=platform&message=mac-intel%20|%20mac-arm%20|%20win-64&color=blue)
[![license](https://img.shields.io/github/license/miyako/4d-plugin-HL7)](LICENSE)
![downloads](https://img.shields.io/github/downloads/miyako/4d-plugin-HL7/total)

# 4d-plugin-HL7

The HL7 plugin parses a raw HL7 v2 message into a 4D `Object`, so you can read segments, fields, repetitions, components, and subcomponents as ordinary object properties and collections instead of hand-splitting the message yourself on `|`, `~`, `^`, and `&`. It's a thin wrapper around the open-source [jcomellas/hl7parser](https://github.com/jcomellas/hl7parser) C library, and it does not validate that the input conforms to any particular HL7 message type (ADT, ORU, etc.) — it decomposes whatever segment/field/repetition/component/subcomponent structure it finds, generically, for any HL7 v2-shaped text.

| Command | Returns | Purpose |
|---|---|---|
| [`HL7 Parse`](#hl7-parse) | `Object` | Parses a raw HL7 v2 message into a nested object/collection structure. |

**Platforms:** macOS (Intel & Apple Silicon), Windows (64-bit).

---

## Requirements & platform notes

- **One mandatory parameter, no optional form.** `HL7 Parse` takes exactly one `Text` parameter — the full raw message — and always returns an `Object`. There's nothing to configure (no delimiter overrides, no message-type hints).
- **Segments must be separated by `\r` (carriage return), not `\n` or `\r\n`.** This is the HL7 v2 wire-format standard, and it's what the underlying parser looks for by default. If you load a message from a file or a system where line endings were normalized to `\n` (which is easy to end up with — text editors, some file-transfer paths, and `Convert string` operations can all do this), the parser won't see multiple segments at all: everything after the first `\r`-less line break gets absorbed as extra field data on the *previous* segment instead of starting a new one. If your source may have been through such a conversion, restore `\r` between segments before calling `HL7 Parse`.
- **The default HL7 encoding characters are assumed.** Field `|`, component `^`, repetition `~`, subcomponent `&`, and escape `\` are hardcoded. If a message declares different encoding characters in its own MSH segment, this plugin does not read that declaration back — the built-in defaults are used regardless.
- **The command does not validate HL7 structure and essentially cannot report a syntax error.** Empty text and completely non-HL7 text both come back as `success:true` with no `HL7` property in the result, rather than `success:false`. Always check for the presence of `HL7` before reading it — don't rely on `success` alone to mean "produced a usable result."
- **Empty fields/components/subcomponents are dropped, not represented as empty text.** If a field like `A^^^B` has two empty components in the middle, the resulting `component` collection contains exactly two entries — `"A"` and `"B"` — not four with two blanks. Don't assume a fixed index in the collection corresponds to a fixed HL7 position; if you need positional meaning (e.g., "PID-3 component 4 is always the assigning authority"), you have to account for this compaction yourself.
- **`error` is only present as of this build.** In the originally reviewed source, an exception thrown while building the result (extremely large messages, out-of-memory) could leave the command hanging the host instead of returning at all. That's been fixed to always return `{success: false, error: "..."}` in that case — but this behavior is only true once you've rebuilt the plugin from the corrected source. If you're running an older compiled build, this specific `error` key may not appear at all, and an out-of-memory condition during parsing may behave differently.

---

## HL7 Parse

### Syntax

```4d
status:=HL7 Parse(message)
```

| Parameter | Type | Description |
|---|---|---|
| `message` | Text | The full raw HL7 v2 message, with segments separated by `\r`. |
| Result | Object | The parse result — see shape below. |

### Description

`HL7 Parse` walks the message's segment/field/repetition/component/subcomponent hierarchy and rebuilds it as nested 4D objects and collections. The result object always has:

| Property | Type | Description |
|---|---|---|
| `success` | Boolean | `true` if the parser ran without an internal error. See the caveat above — this does **not** mean the text was valid HL7, only that parsing didn't fail outright. |
| `error` | Text | Present only on the (rare) internal-error path. Holds a diagnostic message. Not present on ordinary success, and not present if the input simply wasn't recognizable as HL7 (that case is still `success:true`, with no `HL7` property — see below). |
| `HL7` | Collection | Present only when at least one segment was found. One entry per segment, in the order they appeared in the message. |

Each entry in `HL7` is an `Object` with exactly **one property**, whose name is the segment's own ID (`MSH`, `PID`, `NK1`, `PV1`, `OBX`, etc., read straight from the message — not a fixed list of names the plugin knows about). That property's value is a `Collection` of the segment's fields, in order, starting from field 1 (the segment ID itself, field 0, is consumed to become the property name and doesn't appear again as a value).

Each field entry is one of:
- **`Text`** — the field's literal value, already unescaped (see below), if it has no repetition/component/subcomponent structure.
- **`Object`** — `{repetition: Collection}`, if the field decomposes further. Every non-trivial field goes through this `repetition` wrapper even if the message only uses one repetition — it's not conditional on the field actually containing a `~`.

The same pattern repeats one level down: each entry of a `repetition` collection is either `Text` or `{component: Collection}`; each entry of a `component` collection is either `Text` or `{subcomponent: Collection}`; each entry of a `subcomponent` collection is always `Text`.

**Escape sequences are resolved automatically** in every `Text` value, at every level, using the standard HL7 encoding characters:

| Sequence | Becomes |
|---|---|
| `\F\` | `\|` |
| `\R\` | `~` |
| `\S\` | `^` |
| `\T\` | `&` |
| `\E\` | `\` |
| `\.br\` | carriage return |
| `\X0A\` | line feed |
| `\X0D\` | carriage return |

### Example

From the plugin's own test method (`TEST.4dm`):

```4d
//%attributes = {}
$msg:=Folder(fk resources folder).file("test.hl7").getText("utf-8")
$status:=HL7 Parse($msg)
```

Reading a specific field back out — the patient name (PID-5) from a typical ADT message, where the field decomposes into a repetition of one component set:

```4d
$msg:=Folder(fk resources folder).file("test.hl7").getText("utf-8")
$status:=HL7 Parse($msg)

If ($status.success) & (Value type($status.HL7)=Is collection)
	For each ($segment; $status.HL7)
		$segmentName:=OB Keys($segment)[0]
		If ($segmentName="PID")
			$fields:=$segment[$segmentName]
			// PID-5 (patient name) is field index 4 once the segment ID itself is excluded
			$name:=$fields[4]
			If (Value type($name)=Is object)
				$components:=$name.repetition[0].component
				ALERT("Family name: "+String($components[0])+", Given name: "+String($components[1]))
			End if 
		End if 
	End for each 
End if 
```

A generic dispatcher that prints every segment and field regardless of message type, using `Case of` on the value's own type rather than assuming a fixed shape per segment:

```4d
$msg:=Folder(fk resources folder).file("test.hl7").getText("utf-8")
$status:=HL7 Parse($msg)

If ($status.success) & (Value type($status.HL7)=Is collection)
	For each ($segment; $status.HL7)
		$segmentName:=OB Keys($segment)[0]
		$fields:=$segment[$segmentName]
		For each ($field; $fields)
			Case of 
				: (Value type($field)=Is text)
					// plain field value
				: (Value type($field)=Is object)
					// {repetition: Collection} - descend further if needed
			End case 
		End for each 
	End for each 
End if 
```

---

## Error handling & troubleshooting

- **`success:true` with no `HL7` property means nothing was recognized as a segment.** This happens for empty text and for text that doesn't look like HL7 at all — the plugin does not turn this into `success:false`. Always test for the `HL7` property before iterating over it.
- **Segments merge together if the message doesn't use `\r` between them.** If everything ends up nested under a single segment object with garbled-looking field values, the most likely cause is `\n`-only or `\r\n` line endings somewhere upstream — restore `\r` as the segment separator before parsing.
- **A field with fewer entries than you expect usually means empty components were dropped, not that the message is malformed.** The parser omits zero-length repetitions/components/subcomponents from their parent collection rather than keeping a placeholder — check by position within what's actually returned, not by the position in the original HL7 text.
- **Custom encoding characters in a message's own MSH segment are not honored.** If a message declares non-default `|^~\&` characters, this plugin still unescapes and splits using the standard defaults, which will produce wrong results for that message.
- **`error` only appears on genuinely unusual internal failures (e.g. running out of memory on a very large message), not on ordinary malformed input** — see the first bullet for the much more common "nothing parsed" case, and see the Requirements note above if you're not yet on a build with this fix.

---

## Quick reference

```4d
$msg:=Folder(fk resources folder).file("test.hl7").getText("utf-8")
$status:=HL7 Parse($msg)

If ($status.success) & (Value type($status.HL7)=Is collection)
	For each ($segment; $status.HL7)
		$segmentName:=OB Keys($segment)[0]
		$fields:=$segment[$segmentName]
		// $fields[0] is field 1 of $segmentName, etc.
	End for each 
Else 
	// no segments recognized, or (post-fix builds only) $status.error set
End if 
```
