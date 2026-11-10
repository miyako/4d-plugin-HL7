# String ownership regression

Run on macOS with the Xcode command-line tools:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_string_ownership.py
```

The test compiles the actual bundled SDK, plugin, JSON helpers and text/array
wrappers. It calls the parser's actual `push_value` function directly; it does not
replace its implementation with a test copy. Parser dependencies are compiled
as C. The C++ sources run with AddressSanitizer and UndefinedBehaviorSanitizer.
All output is temporary; no Xcode build phase, signing, packaging or publication
runs. The `String ownership` workflow runs the same command.

The tracking host implements only the callbacks needed by these tests. It tracks
string allocations, detects reads after disposal and double disposal, and checks
that no string or handle allocations remain at each lifecycle boundary. Object
and collection insertion copy text content; property reads return an owned text
variable; extracting text from that variable borrows its buffer. Object reference
counting and the full 4D engine are not simulated. Both allocated and null empty
string representations are tested; the actual host's representation is not
assumed. This is not a reproduction in a Windows or macOS 4D host.

## Audit evidence

Baseline: `68141b0b069e117fa541185b02bbe1cc623147fa`.
The bundled SDK implementation says `rev : v14`, its public header `rev : v13`;
these comments are not a verified upstream SDK release identifier.

All three tracked command manifests (root and both test-bundle copies) declare
only `HL7 Parse(&T):J`, selector 1, dispatched by `PluginMain` to `HL7_Parse`.
There are no text-array or `&Y` parameters. `&T` is the input text reference;
`J` is the returned object. Text emission follows
`HL7_Parse -> print_message -> print_node -> push_value`.

| First-party path | Exposure | Baseline result / correction |
|---|---|---|
| `push_value` | Every parsed text value | Initial empty descriptor overwritten; initialize Undefined before shallow string assignment. |
| `ob_set_s(wchar_t*, char*)` | Parser exception/error reporting | Same initial descriptor overwrite; same correction. |
| `ob_set_s(char*, char*)` | Dormant helper | Same initial descriptor overwrite; same correction. |
| Both `ob_set_a` overloads | Dormant helpers | Same initial descriptor overwrite; same correction. |
| `ob_get_a` | Dormant helper | Owned property-result variable never cleared; copy text before clearing, also clear non-text results. |

With the same harness on the baseline, the five overwrite cases each left one
orphaned allocation in allocated-empty mode and passed in null-empty mode.
The getter leaked in both modes. Synchronous callback and array lifecycle
controls passed in both modes. After correction all cases pass in both modes.
The getter and parser emission repeat 50 times, and array replacement/shrink
repeats 20 times. Getter coverage includes absent, null-object and non-text
properties. Callback coverage includes independent key ownership and a non-text
command result. Scalar wrappers copy input and use the content setter for output.
Array coverage includes borrowed reads, independent wrapper copies, replacement,
shrink, final clear and rejected type/index assignments retaining caller ownership.

## SDK contract and unchanged paths

`4D Plugin API/4DPluginAPI.c` is compiled by both platform projects:

| API (baseline lines) | Evidence / lifetime |
|---|---|
| `PA_CreateVariable` (3920-4075) | The Unistring case creates an empty owned descriptor; Undefined allocates nothing. |
| `PA_SetStringVariable` (4254-4259) | Sets the type and shallow-assigns the descriptor without disposing an old value. The final `PA_ClearVariable` remains necessary. |
| `PA_GetObjectProperty` (635-651) | Explicitly documents that the returned variable must be cleared. |
| `PA_SetObjectProperty` / `PA_SetCollectionElement` (654-669 / 603-617) | Pass a variable to synchronous `EX_SET_OBJ_VALUE`. The host shim copies text before the caller clears its temporary. |
| `PA_GetStringVariable` (4105-4118) | Uses engine `EX_VARIABLE_TO_STRING`; the shim models the text result as borrowing the owning variable through conversion. |
| `PA_GetStringInArray` (4738-4755) | Returns a borrowed shallow descriptor. |
| `PA_SetStringInArray` (4933-4947) | Accepted assignment disposes the prior element and shallow-transfers the input; rejection does not consume it. |
| `PA_SetUnistring` / `PA_ReturnString` (289-299 / 2600-2603) | Engine-backed content setter, distinct from array transfer. `C_TEXT` owns independent C++ strings and uses this setter for output. |
| `PA_SetStringField` (3742-3755) | Explicit non-owning field setter; no first-party callers. |
| `PA_HasObjectProperty` (681-691) | Borrows the caller's key in a temporary scalar callback alias; the synchronous call finishes before the caller disposes its key. |

`ARRAY_TEXT` is tracked but not compiled by either plugin project and has no
command callers. Its successful output creates a fresh string for each array
element and does not dispose it after transfer. Its input and append/set
overloads copy borrowed buffers into independent C++ strings. No borrowed
insertion, shared-owner reuse or successful-transfer double disposal was found.
All tracked first-party C/C++ source and wrappers were searched, not only manifest
array parameters. No first-party asynchronous string callbacks were found.
Bundled SDK callback helpers are not first-party wrappers and were not rewritten.

The dormant array wrapper does not check allocation/resize failure. The bundled
SDK's resize implementation even updates the logical count after a failed handle
resize (4550-4605). These failure paths were inspected but not injected or claimed
safe; generic allocator hardening or SDK failure rewrites are separate work, not
part of the demonstrated six-path leak correction.

The Xcode Deployment phase signs, packages and notarizes; it was not run.
Validation here is a native macOS host shim, not a full plugin build or actual
4D host execution. Windows and actual 4D runtime behavior remain untested.
