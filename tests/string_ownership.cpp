#include "../4DPlugin-HL7.cpp"
#include "ARRAY_TEXT.h"
#include "PrivateTypes.h"
#include "EntryPoints.h"

#include <cstdlib>
#include <cstring>
#include <map>
#include <stdexcept>

namespace {
bool allocatedEmpty;
bool commandFailure = false;
std::map<PA_Unichar *, size_t> strings;
std::map<PA_Handle, size_t> handles;
std::map<CUTF16String, CUTF16String> properties;
std::vector<CUTF16String> collection;
bool booleanProperty = false;
size_t clearCalls = 0;

void require(bool condition, const char *message)
{
    if (!condition) throw std::runtime_error(message);
}

CUTF16String read(const PA_Unistring &value)
{
    PA_Unichar *buffer = value.fString;
    if (!buffer) {
        require(value.fLength == 0, "null nonempty string");
        return CUTF16String();
    }
    require(strings.count(buffer) != 0, "read after disposal");
    require(strings.at(buffer) == static_cast<size_t>(value.fLength),
            "descriptor length changed");
    return CUTF16String(buffer, value.fLength);
}

PA_Unistring make(const CUTF16String &text)
{
    PA_Unistring result = {};
    if (text.empty() && !allocatedEmpty) return result;
    result.fString = new PA_Unichar[text.size() + 1];
    std::copy(text.begin(), text.end(), result.fString);
    result.fString[text.size()] = 0;
    result.fLength = static_cast<PA_long32>(text.size());
    PA_Unichar *buffer = result.fString;
    strings.emplace(buffer, text.size());
    return result;
}

void dispose(PA_Unistring &value)
{
    PA_Unichar *buffer = value.fString;
    if (buffer) {
        require(strings.erase(buffer) == 1, "double/borrowed disposal");
        delete[] buffer;
    }
    value = {};
}

void clear(PA_Variable &value)
{
    if (value.fType == eVK_Unistring) dispose(value.uValue.fString);
    if (value.fType == eVK_ArrayUnicode && value.uValue.fArray.fData) {
        PA_Handle h = value.uValue.fArray.fData;
        auto elements = reinterpret_cast<PA_Unistring *>(*h);
        for (PA_long32 i = 0; i <= value.uValue.fArray.fNbElements; ++i)
            dispose(elements[i]);
        require(handles.erase(h) == 1, "unknown array handle");
        std::free(*h);
        delete h;
    }
    value = {};
}

void host(short selector, EngineBlock *eb)
{
    switch (selector) {
    case EX_CREATE_UNISTRING:
        eb->fUniString1 = make(CUTF16String(reinterpret_cast<PA_Unichar *>(eb->fHandle)));
        break;
    case EX_DISPOSE_UNISTRING:
        dispose(eb->fUniString1);
        break;
    case EX_SET_UNISTRING:
        dispose(eb->fUniString1);
        eb->fUniString1 = make(CUTF16String(reinterpret_cast<PA_Unichar *>(eb->fHandle)));
        break;
    case EX_CLEAR_VARIABLE:
        ++clearCalls;
        clear(*static_cast<PA_Variable *>(eb->fPtr1));
        break;
    case EX_VARIABLE_TO_STRING:
        eb->fUniString1 = reinterpret_cast<PA_Variable *>(eb->fHandle)->uValue.fString;
        read(eb->fUniString1);
        break;
    case EX_HANDLE_MANAGER: {
        PA_Handle h = eb->fHandle;
        switch (eb->fParam1) {
        case 1:
            h = new char *;
            *h = static_cast<char *>(std::calloc(1, eb->fParam2 ? eb->fParam2 : 1));
            require(*h != nullptr, "test handle allocation failed");
            handles[h] = eb->fParam2;
            eb->fHandle = h;
            break;
        case 2:
            require(handles.erase(h) == 1, "unknown handle disposal");
            std::free(*h);
            delete h;
            break;
        case 3:
            require(handles.count(h) == 1, "unknown handle resize");
            *h = static_cast<char *>(std::realloc(*h, eb->fParam2));
            require(*h != nullptr, "test handle resize failed");
            handles[h] = eb->fParam2;
            break;
        case 4:
            eb->fParam2 = handles.at(h);
            break;
        case 5:
            eb->fParam3 = reinterpret_cast<sLONG_PTR>(*h);
            break;
        case 6:
            break;
        default:
            throw std::runtime_error("unexpected handle operation");
        }
        break;
    }
    case EX_SET_OBJ_VALUE: {
        CUTF16String text = read(static_cast<PA_Variable *>(eb->fPtr2)->uValue.fString);
        if (eb->fShort == eVK_Collection) {
            require(eb->fLongint == static_cast<PA_long32>(collection.size()), "bad append index");
            collection.push_back(text);
        } else {
            properties[read(eb->fUniString1)] = text;
        }
        break;
    }
    case EX_GET_OBJ_VALUE: {
        PA_Variable &value = *static_cast<PA_Variable *>(eb->fPtr2);
        value = {};
        if (eb->fShort == eVK_Collection) {
            PA_SetLongintVariable(&value, static_cast<PA_long32>(collection.size()));
        } else if (booleanProperty) {
            PA_SetBooleanVariable(&value, true);
        } else {
            PA_Unistring text = make(properties.at(read(eb->fUniString1)));
            PA_SetStringVariable(&value, &text);
        }
        break;
    }
    case EX_EXECUTE_COMMAND_BY_ID: {
        auto params = static_cast<PA_Variable **>(eb->fPtr1);
        PA_Variable &result = *static_cast<PA_Variable *>(eb->fPtr2);
        result = {};
        if (eb->fParam1 == 1231) {
            CUTF16String key = read(params[1]->uValue.fString);
            PA_SetBooleanVariable(&result, properties.count(key) != 0);
        } else if (eb->fParam1 == 1225) {
            PA_SetObjectVariable(&result, PA_GetObjectVariable(*params[0]));
        } else if (eb->fParam1 == 1217) {
            if (!commandFailure) {
                PA_Unistring text = make(CUTF16String(1, 'J'));
                PA_SetStringVariable(&result, &text);
            }
        } else {
            throw std::runtime_error("unexpected command callback");
        }
        break;
    }
    default:
        throw std::runtime_error("unexpected host selector");
    }
}

void noOwners()
{
    require(strings.empty(), "orphaned string allocation");
    require(handles.empty(), "orphaned handle allocation");
}

void run(const std::string &test)
{
    PA_ObjectRef object = reinterpret_cast<PA_ObjectRef>(&properties);
    CUTF16String expected(1, 'x');
    if (test == "push") {
        for (int i = 0; i < 50; ++i) {
            HL7_Node node = {};
            char text[] = "x\\F\\y";
            node.element.value = text;
            node.element.length = sizeof(text) - 1;
            push_value(reinterpret_cast<PA_CollectionRef>(&collection), &node);
            require(collection.back() == CUTF16String({'x', '|', 'y'}), "append changed text");
            noOwners();
        }
    } else if (test == "narrow") {
        ob_set_s(object, "key", "x");
    } else if (test == "wide-utf8") {
        ob_set_s(object, L"key", "x");
    } else if (test == "wide") {
        ob_set_a(object, L"key", L"x");
    } else if (test == "utf16") {
        ob_set_a(object, L"key", &expected);
    } else if (test == "getter") {
        properties[CUTF16String({'k', 'e', 'y'})] = expected;
        for (int i = 0; i < 50; ++i) {
            CUTF8String output;
            require(ob_get_a(object, L"key", &output), "missing property");
            require(output == CUTF8String(1, 'x'), "getter changed text");
            noOwners();
        }
        booleanProperty = true;
        CUTF8String unchanged(1, 'z');
        size_t before = clearCalls;
        require(ob_get_a(object, L"key", &unchanged), "non-string property not found");
        require(clearCalls == before + 1, "non-string result not cleared");
        require(unchanged == CUTF8String(1, 'z'), "non-string changed output");
        require(!ob_get_a(object, L"missing", &unchanged), "missing property found");
        require(!ob_get_a(nullptr, L"key", &unchanged), "null object found");
    } else if (test == "callback") {
        PA_Unistring key = make(CUTF16String({'k', 'e', 'y'}));
        properties[read(key)] = expected;
        PA_Unichar *owner = key.fString;
        require(PA_HasObjectProperty(object, &key), "synchronous callback failed");
        require(key.fString == owner && read(key).size() == 3, "callback consumed borrowed key");
        PA_DisposeUnistring(&key);
        CUTF8String output;
        ob_stringify(object, &output);
        require(output == CUTF8String(1, 'J'), "stringify callback result");
        noOwners();
        commandFailure = true;
        ob_stringify(object, &output);
    } else if (test == "scalar") {
        PA_Unistring parameter = make(expected);
        PA_Unistring *parameters[] = {&parameter};
        C_TEXT wrapper;
        wrapper.fromParamAtIndex(reinterpret_cast<PackagePtr>(parameters), 1);
        PA_DisposeUnistring(&parameter);
        parameter = make(CUTF16String());
        wrapper.toParamAtIndex(reinterpret_cast<PackagePtr>(parameters), 1);
        require(read(parameter) == expected, "scalar input retained borrowed storage");
        PA_Unistring result = make(CUTF16String());
        PA_Unistring *resultPointer = &result;
        wrapper.setReturn(reinterpret_cast<sLONG_PTR *>(&resultPointer));
        PA_DisposeUnistring(&parameter);
        require(read(result) == expected, "scalar return retained wrapper storage");
        PA_DisposeUnistring(&result);
    } else if (test == "array") {
        PA_Variable array = PA_CreateVariable(eVK_ArrayUnicode);
        PA_Variable *parameters[] = {&array};
        for (int iteration = 0; iteration < 20; ++iteration) {
            ARRAY_TEXT wrapper;
            wrapper.appendUTF16String(expected.c_str());
            wrapper.appendUTF16String(expected.c_str());
            wrapper.toParamAtIndex(reinterpret_cast<PackagePtr>(parameters), 1);
            PA_Unistring borrowed = PA_GetStringInArray(array, 1);
            require(read(borrowed) == expected, "array lost transferred text");
            ARRAY_TEXT copy;
            copy.fromParamAtIndex(reinterpret_cast<PackagePtr>(parameters), 1);
            PA_ResizeArray(&array, 0);
            CUTF16String independent;
            copy.copyUTF16StringAtIndex(&independent, 1);
            require(independent == expected, "array wrapper retained borrowed storage");
        }
        PA_ClearVariable(&array);
        PA_Unistring owned = make(expected);
        PA_Variable rejected = PA_CreateVariable(eVK_Undefined);
        PA_SetStringInArray(rejected, 0, &owned);
        require(read(owned) == expected, "invalid type consumed string");
        array = PA_CreateVariable(eVK_ArrayUnicode);
        PA_SetStringInArray(array, -1, &owned);
        PA_SetStringInArray(array, 1, &owned);
        require(read(owned) == expected, "invalid index consumed string");
        PA_ClearVariable(&array);
        PA_DisposeUnistring(&owned);
    } else {
        throw std::runtime_error("unknown test");
    }
    if (test == "narrow" || test == "wide-utf8" || test == "wide" || test == "utf16")
        require(properties.at(CUTF16String({'k', 'e', 'y'})) == expected, "setter changed text");
    noOwners();
}
}

int main(int argc, char **argv)
{
    try {
        require(argc == 3, "usage: string-ownership CASE allocated|null");
        allocatedEmpty = std::string(argv[2]) == "allocated";
        gCall4D = host;
        run(argv[1]);
        std::cout << argv[1] << "/" << argv[2] << ": PASS\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << argv[1] << "/" << argv[2] << ": " << error.what()
                  << " (live strings=" << strings.size() << ")\n";
        return 1;
    }
}
