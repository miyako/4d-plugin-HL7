/* --------------------------------------------------------------------------------
 #
 #  4DPlugin-HL7.cpp
 #	source generated by 4D Plugin Wizard
 #	Project : HL7
 #	author : miyako
 #	2022/06/05
 #  
 # --------------------------------------------------------------------------------*/

#include "4DPlugin-HL7.h"

#pragma mark -

void PluginMain(PA_long32 selector, PA_PluginParameters params) {
    
	try
	{
        switch(selector)
        {
			// --- HL7
            
			case 1 :
				HL7_Parse(params);
				break;

        }

	}
	catch(...)
	{

	}
}

#pragma mark -

#include <regex>

static void unescape(std::string& value) {
        
    value = std::regex_replace(value, std::regex("\\\\F\\\\"), "|");
    value = std::regex_replace(value, std::regex("\\\\R\\\\"), "~");
    value = std::regex_replace(value, std::regex("\\\\S\\\\"), "^");
    value = std::regex_replace(value, std::regex("\\\\T\\\\"), "&");
    
    value = std::regex_replace(value, std::regex("\\\\.br\\\\"), "\r");
    value = std::regex_replace(value, std::regex("\\\\X0A\\\\"), "\n");
    value = std::regex_replace(value, std::regex("\\\\X0D\\\\"), "\r");

    value = std::regex_replace(value, std::regex("\\\\E\\\\"), "\\");
}

static void push_value(PA_CollectionRef c, HL7_Node *node) {
    
    std::string value = std::string(node->element.value, node->element.length);
    unescape(value);
    
    C_TEXT t;
    t.setUTF8String((const uint8_t *)value.c_str(), value.length());
    PA_Variable v = PA_CreateVariable(eVK_Unistring);
    PA_Unistring u = PA_CreateUnistring((PA_Unichar *)t.getUTF16StringPtr());
    PA_SetStringVariable(&v, &u);
    PA_SetCollectionElement(c, PA_GetCollectionLength(c), v);
    PA_ClearVariable(&v);
}

static void print_node(PA_ObjectRef hl7, HL7_Node *node, HL7_Element_Type element_type)
{
    if(node != 0) {
                
        PA_CollectionRef c = PA_CreateCollection();
        
        std::string fieldName;
        
        do
        {
            if (node->element.length > 0) {
                    
                if(element_type == HL7_ELEMENT_FIELD) {
                    if(fieldName.length() == 0) {
                        fieldName = std::string(node->element.value, node->element.length);
                    }else{
                        push_value(c, node);
                    }
                }else{
                    push_value(c, node);
                }
  
            }

            if (node->children != 0) {
                
                    PA_ObjectRef o = PA_CreateObject();
                    print_node(o, node->children, hl7_child_type(element_type));
                    PA_Variable v = PA_CreateVariable(eVK_Object);
                    PA_SetObjectVariable(&v, o);
                    PA_SetCollectionElement(c, PA_GetCollectionLength(c), v);
                    PA_ClearVariable(&v);
 
            }
            node = node->sibling;
            
        } while (node != 0);
        
        switch (element_type) {
            case HL7_ELEMENT_SUBCOMPONENT:
                ob_set_c(hl7, "subcomponent", c);
                break;
            case HL7_ELEMENT_COMPONENT:
                ob_set_c(hl7, "component", c);
                break;
            case HL7_ELEMENT_REPETITION:
                ob_set_c(hl7, "repetition", c);
                break;
            case HL7_ELEMENT_FIELD:
                ob_set_c(hl7, fieldName.c_str(), c);
                break;
            case HL7_ELEMENT_SEGMENT:
                ob_set_c(hl7, "HL7", c);
                break;
            case HL7_ELEMENT_TYPE_COUNT:
                ob_set_c(hl7, "count", c);
                break;
            default:
                break;
        }
    }
}

static void print_message(PA_ObjectRef hl7, HL7_Message *message) {
    
    if(message != 0) {
        print_node(hl7, message->head, HL7_ELEMENT_SEGMENT);
    }
    
}

void HL7_Parse(PA_PluginParameters params) {

    PA_ObjectRef status = PA_CreateObject();
    
    sLONG_PTR *pResult = (sLONG_PTR *)params->fResult;
    PackagePtr pParams = (PackagePtr)params->fParameters;
    
    ob_set_b(status, L"success", false);

    C_TEXT t;
    t.fromParamAtIndex(pParams, 1);
    
    CUTF8String u8;
    t.copyUTF8String(&u8);
    
    HL7_Settings settings;
    hl7_settings_init(&settings);
    
    HL7_Buffer input_buffer;
    size_t message_length = u8.length();
    
    hl7_buffer_init(&input_buffer, (char *)u8.c_str(), message_length);
    hl7_buffer_move_wr_ptr(&input_buffer, message_length);
    
    HL7_Allocator allocator;
    HL7_Message message;
    
    hl7_allocator_init(&allocator, malloc, free);
    hl7_message_init(&message, &settings, &allocator);

    HL7_Parser parser;
    
    hl7_parser_init(&parser, &settings);
    
    if (hl7_parser_read(&parser, &message, &input_buffer) == 0) {
        ob_set_b(status, L"success", true);
        print_message(status, &message);
    }

    hl7_parser_fini(&parser);
    hl7_message_fini(&message);
    hl7_allocator_fini(&allocator);
    hl7_buffer_fini(&input_buffer);
    hl7_settings_fini(&settings);
    
    PA_ReturnObject(params, status);
}
