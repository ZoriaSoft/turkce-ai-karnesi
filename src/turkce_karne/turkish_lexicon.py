"""Small built-in Turkish lexicon for the ``turkish_share`` heuristic.

Deliberately compact: function words, common affix-bearing forms and stems a
model is likely to produce in formal/everyday Turkish. Contributors can add
entries; keep it a sorted set of lowercase words (use the ASCII-folded form
only when the word is unambiguous).
"""

TURKISH_WORDS: frozenset[str] = frozenset(
    {
        # function words / connectives
        "ve", "ile", "için", "ama", "fakat", "ancak", "çünkü", "eğer", "ya",
        "hem", "veya", "veyahut", "ki", "de", "da", "ise", "mi", "mı", "mu",
        "mü", "gibi", "kadar", "daha", "en", "çok", "az", "sonra", "önce",
        "şimdi", "bugün", "dün", "yarın", "burada", "orada", "şurada",
        "böyle", "şöyle", "öyle", "nasıl", "neden", "niçin", "ne", "kim",
        "hangi", "kaç", "bazı", "bütün", "tüm", "her", "hiç", "sadece",
        "yalnızca", "bile", "hatta", "artık", "henüz", "zaten", "yine",
        "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz",
        "on", "yüz", "bin", "milyon",
        # pronouns / copula forms
        "ben", "sen", "o", "biz", "siz", "onlar", "bu", "şu", "bunu", "şunu",
        "onu", "beni", "seni", "benim", "senin", "onun", "bizim", "sizin",
        "kendi", "bana", "sana", "ona", "bize", "size", "benden", "senden",
        "im", "ım", "um", "üm", "sin", "sın", "sun", "sün", "dir", "dır",
        "dur", "dür", "tir", "tır", "tur", "tür", "yim", "yım", "yum", "yüm",
        # common verbs (stems + frequent inflected forms)
        "var", "yok", "oldu", "olan", "olarak", "olur", "olacak", "olmak",
        "yapmak", "yaptı", "yapıldı", "yapılacak", "yaparak", "yapıp",
        "gelmek", "geldi", "gelecek", "gelen", "gitmek", "gitti", "gidecek",
        "almak", "aldı", "alın", "alıyorum", "vermek", "verdi", "verilecek",
        "demek", "dedi", "diyor", "görmek", "gördü", "gördüm", "bilmek",
        "biliyorum", "bilir", "istemek", "istiyorum", "istediğim", "isterim",
        "gerekmek", "gerekiyor", "gereken", "gerekir", "gerekli",
        "bulmak", "bulunan", "bulundu", "bulunmaktadır", "kalmak", "kaldı",
        "çalışmak", "çalışıyor", "çalışıyorum", "başlamak", "başladı",
        "beklemek", "bekliyoruz", "bekleriz", "etmek", "etti", "edecek",
        "olunur", "olunsun", "olsun", "olmasını", "rica", "arz",
        "bilgilerinize", "saygılarımla", "saygılarımızla", "saygılarımızla",
        # nouns / everyday stems
        "gün", "saat", "yıl", "ay", "hafta", "zaman", "iş", "ev", "okul",
        "şehir", "ülke", "insan", "kişi", "çocuk", "kadın", "erkek", "aile",
        "su", "yol", "yer", "taraf", "el", "göz", "baş", "son", "orta",
        "bilgi", "konu", "durum", "soru", "cevap", "sonuç", "rapor", "belge",
        "dosya", "tarih", "saat", "fiyat", "ürün", "hizmet", "müşteri",
        "şirket", "firma", "kurum", "belediye", "üniversite", "öğrenci",
        "öğretmen", "müdür", "başkan", "ekip", "proje", "toplantı", "karar",
        "madde", "özet", "metin", "e-posta", "eposta", "dilekçe", "başvuru",
        "numara", "tutar", "fatura", "abone", "tutanak", "ekip", "sokak",
        "mahalle", "cadde", "adres", "telefon", "ad", "soyad", "isim",
        # adjectives
        "büyük", "küçük", "yeni", "eski", "iyi", "kötü", "güzel", "önemli",
        "farklı", "aynı", "başka", "diğer", "ilk", "son", "uzun", "kısa",
        "kolay", "zor", "hızlı", "yavaş", "doğru", "yanlış", "açık", "kapalı",
        "tam", "eksik", "fazla", "resmi", "acil", "gerekli", "mümkün",
        "uygun", "mevcut", "ilgili", "sayın", "değerli",
        # derived forms that show up constantly in formal text
        "tarafınızdan", "tarafımdan", "tarafımca", "tarafınıza", "tarafından",
        "hakkında", "iletişim", "teşekkür", "teşekkürler", "teşekkür",
        "ederim", "ederiz", "ediyorum", "ediyoruz", "edildi", "edilecek",
        "olarak", "olup", "olmadığı", "olduğunu", "olduğu", "olduğundan",
        "yapılması", "yapılmasını", "yapıldığını", "yapılan", "yapmanız",
        "aldığım", "aldığımız", "aldım", "aldık", "verdiğiniz", "verilen",
        "istiyoruz", "istiyorum", "arzederim", "ricaederim",
        "gerekmektedir", "gerektiğini", "gerektiği", "bulunmaktadır",
        "konusunda", "konusunu", "konunun", "konuya", "konuyu",
        "saygılarımla", "bilgilerinize", "ricaederim",
    }
)
