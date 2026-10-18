"""Small built-in Turkish lexicon for heuristics.

Two consumers:

- ``turkish_share`` counts tokens found here (or bearing Turkish-specific
  characters) as Turkish.
- ``spelling_rules`` mi-harmony uses membership as a "this stem is
  Turkish" signal when checking the question particle's vowel.

Deliberately compact: function words, common affix-bearing forms and
stems a model is likely to produce in formal/everyday Turkish. Entries
are lowercase Turkish (use ``norm_text``-folded forms — ASCII-folded
only when unambiguous). Contributors can add entries; keep them sorted
inside each section comment.
"""

TURKISH_WORDS: frozenset[str] = frozenset(
    {
        # function words / connectives
        "ve", "ile", "için", "ama", "fakat", "ancak", "çünkü", "eğer",
        "ya", "hem", "veya", "veyahut", "ki", "de", "da", "ise",
        "mi", "mı", "mu", "mü", "gibi", "kadar", "daha", "en",
        "çok", "az", "sonra", "önce", "şimdi", "bugün", "dün", "yarın",
        "burada", "orada", "şurada", "böyle", "şöyle", "öyle", "nasıl", "neden",
        "niçin", "ne", "kim", "hangi", "kaç", "bazı", "bütün", "tüm",
        "her", "hiç", "sadece", "yalnızca", "bile", "hatta", "artık", "henüz",
        "zaten", "yine", "bir", "iki", "üç", "dört", "beş", "altı",
        "yedi", "sekiz", "dokuz", "on", "yüz", "bin", "milyon", "aynı",
        "başka", "diğer", "kendi", "belki", "madem", "oysa", "sanki", "üstelik",
        "dahası", "yoksa", "acaba", "galiba", "sanırım", "muhtemelen", "kesinlikle", "tabii",
        "elbette", "maalesef", "ne yazık ki", "aslında", "gerçekten", "özellikle", "genellikle", "çoğunlukla",
        "bazen", "sık sık", "nadiren", "asla", "hemen", "yavaş yavaş", "birden", "aniden",
        # pronouns / copula forms
        "ben", "sen", "o", "biz", "siz", "onlar", "bu", "şu",
        "bunu", "şunu", "onu", "beni", "seni", "benim", "senin", "onun",
        "bizim", "sizin", "bana", "sana", "ona", "bize", "size", "benden",
        "senden", "im", "ım", "um", "üm", "sin", "sın", "sun",
        "sün", "dir", "dır", "dur", "dür", "tir", "tır", "tur",
        "tür", "yim", "yım", "yum", "yüm", "bende", "sende", "onda",
        "bizde", "sizde", "onlarda", "bunda", "şunda", "benimle", "seninle", "onunla",
        "bizimle", "sizinle", "onlarla", "benimki", "seninki", "onunki", "bizimki", "sizinki",
        "hepimiz", "hepiniz", "hepsi", "hiçbiri", "hiçbirimiz", "birçok",
        # common verbs (stems + frequent inflected forms)
        "var", "yok", "oldu", "olan", "olarak", "olur", "olacak", "olmak",
        "yapmak", "yaptı", "yapıldı", "yapılacak", "yaparak", "yapıp", "gelmek", "geldi",
        "gelecek", "gelen", "gitmek", "gitti", "gidecek", "almak", "aldı", "alın",
        "alıyorum", "vermek", "verdi", "verilecek", "demek", "dedi", "diyor", "görmek",
        "gördü", "gördüm", "bilmek", "biliyorum", "bilir", "istemek", "istiyorum", "istediğim",
        "isterim", "gerekmek", "gerekiyor", "gereken", "gerekir", "gerekli", "bulmak", "bulunan",
        "bulundu", "bulunmaktadır", "kalmak", "kaldı", "çalışmak", "çalışıyor", "çalışıyorum", "başlamak",
        "başladı", "beklemek", "bekliyoruz", "bekleriz", "etmek", "etti", "edecek", "olunur",
        "olunsun", "olsun", "olmasını", "rica", "arz", "bilgilerinize", "saygılarımla", "saygılarımızla",
        "söylemek", "söyledi", "söylüyor", "söylendi", "anlamak", "anladı", "anlıyorum", "düşünmek",
        "düşündü", "düşünüyorum", "düşünüyor", "bakmak", "baktı", "bakıyor", "girmek", "girdi",
        "çıkmak", "çıktı", "durmak", "durdu", "koymak", "koydu", "buldu", "buluyor",
        "yazmak", "yazdı", "yazıyor", "okumak", "okudu", "okuyor", "konusmak", "konuştu",
        "konuşuyor", "dinlemek", "dinledi", "sormak", "sordu", "soruyor", "cevaplamak", "cevapladı",
        "yardımcı", "yardım", "yardımcı olmak", "destek", "desteklemek", "geldim", "gittim", "aldım",
        "verdim", "yaptım", "oldum", "dedim", "bildim", "istedim", "geldik", "gittik",
        "aldık", "gelir", "gider", "alır", "verir", "yapar", "eder", "geliyor",
        "gidiyor", "alıyor", "veriyor", "yapıyor", "ediyor", "gelmiş", "gitmiş", "almış",
        "vermiş", "yapmış", "olmuş", "etmiş", "geliyorum", "gidiyorum", "veriyorum", "yapıyorum",
        "alacak", "verecek", "yapacak", "geleceğim", "gideceğim", "alacağım", "vereceğim", "yapacağım",
        "gelebiliriz", "gidebiliriz", "alabiliriz", "yapabiliriz", "bilirim", "bilirsin", "biliriz", "bilirler",
        "bilmiyorum", "unutmak", "unuttu", "hatırlamak", "hatırladı", "hatırlıyorum", "denemek", "denedi",
        "deniyor", "kullanmak", "kullandı", "kullanıyor", "buluşmak", "buluştu", "buluşuyoruz", "tanışmak",
        "tanıştı", "oturmak", "oturdu", "kalkmak", "kalktı", "yatmak", "yattı", "uyanmak",
        "uyandı", "yemek", "içmek", "içti", "koşmak", "koştu", "yürümek", "yürüdü",
        "binmek", "bindi", "inmek", "indi", "bekledim", "bekledik", "bekliyorum", "aradım",
        "aradık", "arıyorum", "açtık", "açtı", "kapattık", "kapattı", "başladık", "bitirdik",
        "getirdim", "götürdüm", "gönderdim", "aldırdım", "yolladım",
        # nouns / everyday stems
        "gün", "saat", "yıl", "ay", "hafta", "zaman", "iş", "ev",
        "okul", "şehir", "ülke", "insan", "kişi", "çocuk", "kadın", "erkek",
        "aile", "su", "yol", "yer", "taraf", "el", "göz", "baş",
        "son", "orta", "bilgi", "konu", "durum", "soru", "cevap", "sonuç",
        "rapor", "belge", "dosya", "tarih", "fiyat", "ürün", "hizmet", "müşteri",
        "şirket", "firma", "kurum", "belediye", "üniversite", "öğrenci", "öğretmen", "müdür",
        "başkan", "ekip", "proje", "toplantı", "karar", "madde", "özet", "metin",
        "e-posta", "eposta", "dilekçe", "başvuru", "numara", "tutar", "fatura", "abone",
        "tutanak", "sokak", "mahalle", "cadde", "adres", "telefon", "ad", "soyad",
        "isim", "akşam", "sabah", "öğle", "gece", "mevsim", "hafta sonu", "gündüz",
        "pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar", "ocak",
        "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül",
        "ekim", "kasım", "aralık", "para", "hesap", "banka", "kredi", "borç",
        "ödeme", "sipariş", "paket", "kargo", "kutu", "çanta", "anahtar", "kapı",
        "pencere", "masa", "sandalye", "oda", "mutfak", "banyo", "salon", "bahçe",
        "araba", "otobüs", "tren", "uçak", "vapur", "gemi", "yolcu", "bilet",
        "durak", "istasyon", "havalimanı", "liman", "köprü", "park", "meydan", "bulvar",
        "köy", "kitap", "defter", "kalem", "kağıt", "gazete", "dergi", "mektup",
        "mesaj", "mail", "bilgisayar", "ekran", "klavye", "fare", "yazıcı", "klasör",
        "evrak", "resim", "fotoğraf", "müzik", "film", "dizi", "oyun", "maç",
        "spor", "takım", "oyuncu", "hoca", "antrenör", "hakem", "seyirci", "çorba",
        "ekmek", "peynir", "zeytin", "yumurta", "süt", "çay", "kahve", "meyve",
        "sebze", "et", "tavuk", "balık", "pilav", "makarna", "salata", "tatlı",
        "baklava", "börek", "hastane", "doktor", "hemşire", "hasta", "ilaç", "reçete",
        "randevu", "ameliyat", "sağlık", "hastalık", "ağrı", "ateş", "tansiyon", "polis",
        "asker", "avukat", "hakim", "savcı", "memur", "işçi", "esnaf", "tüccar",
        "çiftçi", "şoför", "aşçı", "garson", "mühendis", "teknisyen", "uzman", "danışman",
        "sekreter", "arkadaş", "dost", "komşu", "akrab", "akraba", "anne", "baba",
        "kardeş", "abla", "ağabey", "amca", "dayı", "teyze", "hala", "dede",
        "nine", "torun", "eş", "koca", "karı", "nişanlı", "gelin", "damat",
        "bebek", "genç", "yaşlı", "adam", "hanım", "bey",
        # adjectives
        "büyük", "küçük", "yeni", "eski", "iyi", "kötü", "güzel", "önemli",
        "farklı", "ilk", "uzun", "kısa", "kolay", "zor", "hızlı", "yavaş",
        "doğru", "yanlış", "açık", "kapalı", "tam", "eksik", "fazla", "resmi",
        "acil", "mümkün", "uygun", "mevcut", "ilgili", "sayın", "değerli", "değer",
        "zengin", "fakir", "yoksul", "güçlü", "zayıf", "sağlam", "kırık", "boş",
        "dolu", "temiz", "kirli", "düzenli", "düzensiz", "rahat", "dar", "geniş",
        "derin", "sığ", "yüksek", "alçak", "kalın", "ince", "sert", "yumuşak",
        "sıcak", "soğuk", "ılık", "serin", "kuru", "ıslak", "nemli", "parlak",
        "mat", "renkli", "renksiz", "beyaz", "siyah", "kırmızı", "mavi", "yeşil",
        "sarı", "turuncu", "mor", "pembe", "kahverengi", "gri", "lacivert", "turkuaz",
        "bordo", "bej", "krem",
        # derived forms that show up constantly in formal text
        "tarafınızdan", "tarafımdan", "tarafımca", "tarafınıza", "tarafından", "hakkında", "iletişim", "teşekkür",
        "teşekkürler", "ederim", "ederiz", "ediyorum", "ediyoruz", "edildi", "edilecek", "olup",
        "olmadığı", "olduğunu", "olduğu", "olduğundan", "yapılması", "yapılmasını", "yapıldığını", "yapılan",
        "yapmanız", "aldığım", "aldığımız", "verdiğiniz", "verilen", "istiyoruz", "arzederim", "ricaederim",
        "gerekmektedir", "gerektiğini", "gerektiği", "konusunda", "konusunu", "konunun", "konuya", "konuyu",
        "görülmüştür", "bilinmektedir", "yapılmaktadır", "edilmektedir", "gerçekleştirilen", "düzenlenen", "hazırlanan", "sunulan",
        "belirtilen", "belirtilmiştir", "açıklanan", "duyurulan", "saygılarımı", "sunarım", "sunarız",
    }
)
