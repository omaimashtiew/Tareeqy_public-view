NAME_MAPPING = {
    "صرة": "صره",  
    "صره": "صره",  
    "العيزريه": "العيزرية",  
    "العيزرية": "العيزرية", 
    "عين سينا": "عين سينيا",  
    "عين سينيا": "عين سينيا",  
    "زعترا": "زعترة",  
    "زعترة": "زعترة", 
    "زعتره": "زعترة", 
    "الساوية":"الساوية" ,
    "الساويه" :"الساوية" ,
    "المربعه":"المربعه" ,
    "المربعة":"المربعه" ,
    "حواره":"حواره" ,
    "حوارة":"حواره" , 




}
def normalize_name(name):
    normalized_name = name.strip()  
    return NAME_MAPPING.get(normalized_name, normalized_name)

def normalize_names(names):
    return list(set(normalize_name(name) for name in names))