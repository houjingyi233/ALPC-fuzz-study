import re
import os
done = 0

def get_all_py():
    for root,dirs,files in os.walk("D:\\ALPC-FUZZ\\interfaces"):
        myfiles=[]
        for file in files:
            if os.path.splitext(file)[1] == '.py' and file != 'transfer.py':
                myfiles.append(file)
        return myfiles

# first check if the decompile results are right
def check_decompile(file):
    f = open(file, "r+")
    while True:
        str = f.readline()
        # symbol failed to load,go to next file
        if not str:
            f.close()
            return 0
        matchobj = re.search(r'Proc(.*)_(.*)',str)
        # symbol successfully loaded,we can transfer this file
        if matchobj:
            f.close()
            return 1

def transfer(file):
    done = 0
    FirstFunction = 1

    fold = open(file, "r+")
    fnew = open("D:\\ALPC-FUZZ\\transfer\\"+file,"w+")
    finterfaces = open("D:\\ALPC-fuzz\\interfaces\\Endpoints.txt", "r+")

    # print "now transfer "+file
    interface_name=file[:-3]

    # we need this for output topological sort
    struct_str = {}
    struct_dict = {}

    while not done:
        str = fold.readline()
        if(str != ""):

            contain_array = []
            # deal with structure like"typedef struct Struct_x_t"
            matchobj = re.search(r'typedef(.*)Struct_(?P<count>(.*))_t', str)
            if matchobj:
                str = fold.readline()
                struct_name = "Struct_"+matchobj.groupdict()['count']
                struct_str[struct_name] = "class Struct_" + matchobj.groupdict()['count'] + "_t(NdrStructure):\n"
                struct_str[struct_name] += "    MEMBERS = ["

                while(str.find("}") == -1):
                    str = fold.readline()

                    write_str = ""

                    #deal with size_is
                    matchobj = re.search(r'(?P<SizeIs>(size_is\(StructMember(?P<SizeCount>(\d*))\)\]))',str)
                    if matchobj:
                        write_str += "SizeIs("
                        write_str += matchobj.groupdict()['SizeCount']
                        write_str += ")/"

                    #deal with case like "xxx StructMemberx[xxx]"
                    #deal with case like "xxx StructMemberx[xxx][xxx]"
                    matchobj = re.search(r'(?P<type>(small|char|long|byte|wchar_t|short|hyper|struct(.*)Struct_(?P<structcount>(.*))_t))(.*)StructMember(\d*)(\[(?P<arraycount1>(\d*))\])?(\[(?P<arraycount2>(\d*))\])?', str)
                    if matchobj:
                        if matchobj.groupdict()['type'] == "long":
                            write_str += "NdrLong, "
                        if matchobj.groupdict()['type'] == "small":
                            write_str += "NdrSmall, "
                        #just treat char as byte
                        if matchobj.groupdict()['type'] == "byte" or matchobj.groupdict()['type'] == "char":
                            write_str += "NdrByte, "
                        if matchobj.groupdict()['type'] == "wchar_t":
                            if str.find("[string]") != -1:
                                write_str += "NdrWString, "
                            else:
                                write_str += "NdrWChar, "
                        if matchobj.groupdict()['type'] == "short":
                            write_str += "NdrShort, "
                        if matchobj.groupdict()['type'] == "hyper":
                            write_str += "NdrHyper, "
                        if matchobj.groupdict()['type'].find("struct") != -1:
                            write_str += "Struct_" + matchobj.groupdict()['structcount'] + "_t, "
                            contain_name = 'Struct_' + matchobj.groupdict()['structcount']
                            if contain_name not in contain_array:
                                contain_array.append(contain_name)

                        if matchobj.groupdict()['arraycount1'] != None and matchobj.groupdict()['arraycount1'] != "":
                            if matchobj.groupdict()['arraycount2'] != None and matchobj.groupdict()['arraycount2'] != "":
                                number = int(matchobj.groupdict()['arraycount1'])*int(matchobj.groupdict()['arraycount2'])
                            else:
                                number = int(matchobj.groupdict()['arraycount1'])
                            while number:
                                struct_str[struct_name] += write_str
                                number = number - 1
                        else:
                            struct_str[struct_name] += write_str

                    #end
                    matchobj = re.search(r'}Struct_(.*)_t',str)
                    if matchobj:
                        struct_str[struct_name] += "]\n\n"
                        struct_dict[struct_name] = contain_array

            # deal with union like"class Union_x_t(NdrUnion)"
            matchobj = re.search(r'typedef(.*)\[switch_type(?P<type>(.*))\](.*)union(.*)union_(?P<count>(.*))', str)
            if matchobj:
                union_name = "Union_" + matchobj.groupdict()['count']
                struct_str[union_name] = "class Union_" + matchobj.groupdict()['count'] + "_t(NdrUnion):\n"
                struct_str[union_name] += "    SWITCHTYPE = "

                if matchobj.groupdict()['type'].find("double") != -1 \
                or matchobj.groupdict()['type'].find("float") != -1 \
                or matchobj.groupdict()['type'].find("long") != -1 \
                or matchobj.groupdict()['type'].find("__int3264") != -1:
                    struct_str[union_name] += "NdrLong\n"

                if matchobj.groupdict()['type'].find("short") != -1:
                    struct_str[union_name] += "NdrShort\n"

                if matchobj.groupdict()['type'].find("small") != -1:
                    struct_str[union_name] += "NdrSmall\n"

                struct_str[union_name] += "    MEMBERS = {"

                str = fold.readline()

                while(str.find("}") == -1):

                    isunique = 0
                    str = fold.readline()

                    if str.find("no default member") != -1:
                        continue
                    if str.find("An exception will") != -1:
                        continue

                    if str.find("unique") != -1:
                        isunique = 1

                    #ignore default
                    matchobj = re.search(r'\[default\]', str)
                    if matchobj:
                        continue

                    #I really do not know how to deal with cases like"[case(x)] [unique]interface(xxxxxxxx-xxxx-xxxx-xxxxxxxxxx)* unionMember_x"
                    matchobj = re.search(r'interface', str)
                    if matchobj:
                        continue

                    #make sure the serial number
                    matchobj = re.search(r'\[case\((?P<number>(\d*))\)\](.*)', str)
                    if matchobj:
                        struct_str[union_name] += matchobj.groupdict()['number']
                        struct_str[union_name] += ": "

                        #deal with case like"[case(x)] [unique]struct Struct_x_t* unionMember_x"
                        matchobj = re.search(r'struct(.*)Struct_(?P<count>(.*))_t', str)
                        if matchobj:
                            if isunique:
                                struct_str[union_name] += 'NdrUniquePTR(Struct_'+matchobj.groupdict()['count']+'_t), '
                            else:
                                struct_str[union_name] += 'NdrPtr(Struct_' + matchobj.groupdict()['count'] + '_t), '
                            contain_name='Struct_' + matchobj.groupdict()['count']
                            if contain_name not in contain_array:
                                contain_array.append(contain_name)

                        #deal with case like"[case(x)]	hyper unionMember_x"
                        if str.find("hyper") != -1:
                            if isunique:
                                struct_str[union_name] += 'NdrUniquePTR(NdrHyper), '
                            else:
                                struct_str[union_name] += 'NdrHyper, '

                        #deal with case like"[case(x)] float|double|long|__int3264 unionMember_x"
                        if str.find("double") != -1 or str.find("float") != -1 or str.find("long") != -1 or str.find("__int3264") != -1:
                            if isunique:
                                struct_str[union_name] += 'NdrUniquePTR(NdrLong), '
                            else:
                                struct_str[union_name] += 'NdrLong, '

                        #deal with case like"[case(x)] short unionMember_x"
                        if str.find("short") != -1:
                            if isunique:
                                struct_str[union_name] += 'NdrUniquePTR(NdrShort), '
                            else:
                                struct_str[union_name] += 'NdrShort, '

                        #deal with case like"[case(x)] /* FC_ZERO */"
                        #I really do not know how to deal with this
                        if str.find("FC_ZERO") != -1:
                            struct_str[union_name] += '0, '

                        #deal with case like"[case(x)] small unionMember_x"
                        if str.find("small") != -1:
                            if isunique:
                                struct_str[union_name] += 'NdrUniquePTR(NdrSmall), '
                            else:
                                struct_str[union_name] += 'NdrSmall, '

                        #deal with case like"[case(x)]	byte unionMember_x"
                        if str.find("byte") != -1:
                            if isunique:
                                struct_str[union_name] += 'NdrUniquePTR(NdrByte), '
                            else:
                                struct_str[union_name] += 'NdrByte, '

                        #deal with case like"[case(x)] [unique][string] wchar_t** unionMember_x"
                        matchobj = re.search(r'\[unique\]\[string\](.*)wchar_t', str)
                        if matchobj:
                            struct_str[union_name] += 'NdrUniquePTR(NdrWString), '
                        else:
                            #deal with case like"[case(x)] [unique]char *unionMember_x "
                            if str.find("char") != -1:
                                if isunique:
                                    struct_str[union_name] += 'NdrUniquePTR(NdrWChar), '
                                else:
                                    struct_str[union_name] += 'NdrWChar, '

                    #end
                    matchobj = re.search(r'\}(.*)union_(.*)', str)
                    if matchobj:
                        struct_str[union_name] += "}\n\n"
                        struct_dict[union_name] = contain_array
                        break

            # prase function
            matchobj = re.search(r'Proc(.*?)_(?P<function>(.*))\(', str)

            if matchobj:

                # I do not how,there are still many structures used in function not defined
                # I think I just have to ignore these functions
                pos = fold.tell()
                str_temp = fold.readline()
                flag1 = 0
                
                while str_temp.find("Proc") == -1 and str_temp.find("}") == -1:

                    matchobj_temp = re.search(r'\[in\](.*)struct(.*)Struct_(?P<count>(.*))_t', str_temp)

                    if matchobj_temp:
                        struct_str_temp = "Struct_"+matchobj_temp.groupdict()['count']
                        if struct_str.has_key(struct_str_temp) == False:
                            flag1 = 1
                            break

                    str_temp = fold.readline()

                fold.seek(pos, 0)

                # we have to define structure and union after we read them all
                if FirstFunction:
                    fnew.write("from rpc_forge import *\n")
                    while True:
                        flag2 = 0
                        for item in struct_dict:

                            if struct_dict[item] == [] or cmp("".join(struct_dict[item]),item) == 0:
                                fnew.write(struct_str[item])
                                flag2 = 1
                                struct_dict[item] = "NULL"
                                for items in struct_dict:
                                    if item in struct_dict[items]:
                                        struct_dict[items].remove(item)

                        if flag2 == 0:
                            break

                    fnew.write("interface = Interface(\""+interface_name+"\", (1,0), [\n")

                    FirstFunction = 0

                if flag1 == 0:

                    fnew.write("Method(\"" + matchobj.groupdict()["function"] + "\", 1,\n")
                    
                    IsFirstTime = 1
                    
                    while True:
                    
                        In = 0
                        Out = 0
                    
                        brackets = 0
                    
                        # IsRange = 0
                    
                        IsRef = 0
                        IsChar = 0
                        IsLong = 0
                        IsSize = 0
                        IsHyper = 0
                        IsShort = 0
                        IsSmall = 0
                        IsSwitch = 0
                        IsUnique = 0
                        IsStruct = 0
                        IsString = 0
                        IsContext = 0
                    
                        SizeCount = 0
                        UnionCount = 0
                        StructCount = 0
                        SwitchCount = 0
                    
                        str = fold.readline()
                    
                        matchobj = re.search(r'\[(?P<IsIn>(in))\]',str)
                        if matchobj:
                            In = 1
                    
                        # we just ignore out put
                        matchobj = re.search(r'\[(?P<IsOut>(out))\]', str)
                        if matchobj and In == 0:
                            continue
                    
                        matchobj = re.search(r'\[(?P<IsRef>(ref))\]', str)
                        if matchobj:
                            IsRef = 1
                    
                        matchobj = re.search(r'(?P<IsChar>(char|byte))', str)
                        if matchobj:
                            IsChar = 1
                    
                        matchobj = re.search(r'(?P<IsLong>(double|float|long|__int3264))', str)
                        if matchobj:
                            IsLong = 1
                    
                        matchobj = re.search(r'(?P<IsShort>(short))', str)
                        if matchobj:
                            IsShort = 1
                    
                        matchobj = re.search(r'(?P<IsHyper>(hyper))', str)
                        if matchobj:
                            IsHyper = 1
                    
                        matchobj = re.search(r'(?P<IsSmall>(small))', str)
                        if matchobj:
                            IsSmall = 1
                    
                        matchobj = re.search(r'\[(?P<IsSize>(size_is\(arg_(?P<sizecount>(\d*))\)))\]', str)
                        if matchobj:
                            IsSize = 1
                            SizeStr = matchobj.groupdict()["IsSize"]
                            SizeCount = matchobj.groupdict()["sizecount"]
                    
                        # I want to ignore problem about range
                        '''
                        matchobj = re.search(r'\[(?P<IsRange>(range(.*)))\]', str)
                        if matchobj:
                            IsRange = 1
                            RangeStr = matchobj.groupdict()["IsRange"]
                    
                        #this means it is actually commented
                        matchobj = re.search(r'/\*\[(?P<IsRange>(range(.*)))\]\*/', str)
                        if matchobj:
                            IsRange = 0
                        '''
                    
                        matchobj = re.search(r'\[(?P<IsSwitch>(switch_is\(arg_(?P<switchcount>(.*))\)))\]', str)
                        if matchobj:
                            IsSwitch = 1
                            SwitchCount = matchobj.groupdict()["switchcount"]
                            matchobj = re.search(r'(union union_(?P<unioncount>\d*))', str)
                            if matchobj:
                                UnionCount = matchobj.groupdict()["unioncount"]
                            else:
                                print "sth seems wrong.\n"
                                exit()
                    
                        matchobj = re.search(r'\[(?P<IsUnique>(unique))\]', str)
                        if matchobj:
                            IsUnique = 1
                    
                        matchobj = re.search(r'(?P<IsStruct>(struct Struct_(?P<count>(.*))_t))', str)
                        if matchobj:
                            IsStruct = 1
                            StructCount = matchobj.groupdict()["count"]
                    
                        matchobj = re.search(r'\[(?P<IsString>(string))\]', str)
                        if matchobj:
                            IsString = 1
                    
                        matchobj = re.search(r'\[(?P<IsContext>(context_handle))\]', str)
                        if matchobj:
                            IsContext = 1
                    
                        # no in and no out means this function is end
                        if In == 0 and Out == 0:
                            fnew.write("),\n")
                            break
                    
                        if IsFirstTime == 0:
                            fnew.write(",\n")
                    
                        IsFirstTime = 0
                    
                        if In:
                            fnew.write("In(")
                            brackets = brackets + 1
                    
                        if Out:
                            fnew.write("Out(")
                            brackets = brackets + 1
                    
                        if IsRef:
                            fnew.write("NdrRef(")
                            brackets = brackets + 1
                    
                        if IsUnique:
                            fnew.write("NdrUniquePTR(")
                            brackets = brackets + 1
                    
                        '''
                        if IsRange:
                            fnew.write(RangeStr[0].upper()+RangeStr[1:]+" / ")
                        '''
                    
                        if IsSize:
                            fnew.write("SizeIs("+SizeCount+") / ")
                    
                        if IsChar:
                            if IsString == 0:
                                fnew.write("NdrByte")
                    
                        if IsLong:
                            fnew.write("NdrLong")
                    
                        if IsShort:
                            fnew.write("NdrShort")
                    
                        if IsHyper:
                            fnew.write("NdrHyper")
                    
                        if IsSmall:
                            fnew.write("NdrSmall")
                    
                        if IsString:
                            fnew.write("NdrWString")
                    
                        if IsSwitch:
                            fnew.write("SwitchIs("+SwitchCount+") / Union_"+UnionCount+"_t")
                    
                        if IsContext:
                            fnew.write("NdrContextHandle")
                    
                        if IsStruct:
                            fnew.write("Struct_"+StructCount+"_t")
                    
                        while brackets:
                            fnew.write(")")
                            brackets = brackets-1

                fnew.write("\n")

        else:
            done = 1

            fnew.write("])\n\n")
            fnew.write("interface.is_registered = True\n\n")
            fnew.write("interface.endpoints = []\n")

            str = finterfaces.readline()
            str = str.rstrip()
            while (str != ""):
                fnew.write("interface.endpoints.append(\"" + str + "\")\n")
                str = finterfaces.readline()
                str = str.rstrip()
            fnew.close()
            finterfaces.close()


if __name__ == '__main__':
    myfiles = get_all_py()
    for file in myfiles:
        if check_decompile(file):
            transfer(file)