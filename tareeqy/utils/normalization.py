NAME_MAPPING = {
    "العيزريه": "العيزرية",
    "عين سينا": "عين سينيا",
    "زعترا": "زعترة",
    "صرة": "صره",

  
}
def normalize_name(name):
    normalized_name = name.strip()  
    return NAME_MAPPING.get(normalized_name, normalized_name)

def normalize_names(names):
    return list(set(normalize_name(name) for name in names))