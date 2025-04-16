from tareeqy.models import Fence

fence_names = [
    "صره", "دير شرف", "عين سينيا", "روابي", "جبع", "شافي شمرون", "المربعه",
    "بورين", "عورتا", "بزاريا", "الحمرا", "العيزرية", "عناتا", "الكونتينر",
    "يتسهار", "زعترة", "الفندق", "النبي يونس", "سلفيت", "ترمسعيا", "قلنديا",
    "الزعيم", "النشاش", "بيت جالا", "النفق", "الخضر", "حواره", "الباذان",
    "النبي صالح", "بيت ليد", "اريحا", "كفر لاقف", "حارس", "كانا", "بديا",
    "جماعين", "عقربا", "الساوية", "عطارة", "سلواد",
]

for name in fence_names:
    Fence.objects.get_or_create(
        name=name,
        latitude=0,  # Or provide actual latitude values
        longitude=0  # Or provide actual longitude values
    )
