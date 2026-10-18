#!/usr/bin/env python3
"""Generate dataset/v1/cikartim-ocr.yaml — seeded synthetic OCR tasks.

Deterministic: the emitted bytes depend only on this file plus
``turkce_karne.ocrnoise``. Regenerate or verify:

    python3 scripts/gen_ocr_tasks.py            # write the dataset file
    python3 scripts/gen_ocr_tasks.py --stdout   # print to stdout
    python3 scripts/gen_ocr_tasks.py --check    # exit 1 if file is stale

Run from the repository root. Pure stdlib beyond the package itself.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from turkce_karne.ocrnoise import render_document

OUT = ROOT / "dataset" / "v1" / "cikartim-ocr.yaml"

PROMPT = (
    "Aşağıdaki metin bozuk bir taramanın (OCR) çıktısıdır; satırlarda "
    "okuma hataları olabilir. İstenen alanları metnin İFADE ETTİĞİ "
    "değerlerle çıkar ve YALNIZCA JSON yaz (açıklama yok). Alanlar: "
    "{alist}. Tarihleri YYYY-MM-DD biçiminde, tutarları sayı olarak yaz."
)

# field kinds: date | money | num | int | name | text | code | plate
TEMPLATES: list[dict] = [
    {
        "slug": "ocr-fatura",
        "difficulty": 4,
        "check": {"type": "json_fields", "strict": True},
        "fields": {
            "satici_unvan": ("name", "Koza Bilişim ve Elektronik Tic. A.Ş."),
            "fatura_no": ("code", "ETT2026/04127"),
            "tarih": ("date", "2026-10-13"),
            "ara_toplam": ("money", 1869.70),
            "kdv": ("money", 373.94),
            "genel_toplam": ("money", 2243.64),
        },
        "lines": [
            "KOZA BİLİŞİM VE ELEKTRONİK TİC. A.Ş.",
            "Merkez Mah. 718. Sk. No:12 Çankaya/ANKARA",
            "VKN: 2750483160   Mersis: 0275048316000019",
            "e-Arşiv Fatura No: {fatura_no}",
            "Düzenleme Tarihi: {tarih}   Saat: 11:47",
            "----------------------------------------",
            "3x USB-C şarj aleti 25W     449,90   1.349,70",
            "1x Cat6 kablo 30m         520,00     520,00",
            "----------------------------------------",
            "ARA TOPLAM  : {ara_toplam}",
            "KDV (%20)   : {kdv}",
            "GENEL TOPLAM: {genel_toplam}",
            "Ödeme şekli: KREDİ KARTI - provizyon 004291",
            "e-Arşiv başvuru seri no: ETB-7742-31",
        ],
    },
    {
        "slug": "ocr-makbuz",
        "difficulty": 3,
        "check": {"type": "json_fields", "strict": True},
        "fields": {
            "market_adi": ("name", "Deniz Market Gıda Ltd."),
            "fis_no": ("code", "B-0047-2216"),
            "tarih": ("date", "2026-10-15"),
            "urun_sayisi": ("int", 7),
            "toplam": ("money", 412.35),
        },
        "lines": [
            "DENİZ MARKET GIDA LTD. - ŞUBE 3",
            "Fiş No: {fis_no}    Tarih: {tarih}  19:22",
            "Kasiyer: A. YÜKSEL   Kasa: 05",
            "========================================",
            "Süt 1L               47,50",
            "Tam buğday ekmek     32,00",
            "Beyaz peynir 500g   189,90",
            "Yumurta 10lu         84,95",
            "Domates kg           58,00",
            "========================================",
            "Ürün sayısı: {urun_sayisi}",
            "TOPLAM      : {toplam} TL",
            "Nakit: 500,00   Para üstü: 87,65",
            "Barkod: 8 698745 120033",
        ],
    },
    {
        "slug": "ocr-asansor-tutanak",
        "difficulty": 4,
        "check": {
            "type": "json_fields",
            "required": ["tutanak_no", "tarih"],
        },
        "fields": {
            "tutanak_no": ("code", "AST-2026-118"),
            "tarih": ("date", "2026-10-16"),
            "bina_adresi": ("text", "Gül Mah. Lale Sk. No:7 Kadıköy/İSTANBUL"),
            "gorevli": ("name", "Rıfat Kandemir"),
            "ariza_ozeti": ("text", "asansor kabin halati asinmasi"),
        },
        "lines": [
            "ASANSÖR PERİYODİK KONTROL / ARIZA TUTANAĞI",
            "Tutanak No: {tutanak_no}",
            "Tarih: {tarih}    Varış: 10:15",
            "Bina adresi: {bina_adresi}",
            "Bakım görevlisi: {gorevli}",
            "Gözlem: Kabin halatında aşınma ve kabarma tespit",
            "edilmiştir. Fren testi olumsuz sonuç verdi.",
            "Arıza özeti: {ariza_ozeti}",
            "Karar: Asansörün kullanımı, halat değişimi tamamlanana",
            "kadar geçici olarak durdurulmuştur.",
            "Firma kaşe: Tekniklift Bakım San.   İmza: (okunamıyor)",
        ],
    },
    {
        "slug": "ocr-irsaliye",
        "difficulty": 3,
        "check": {"type": "json_fields", "strict": True},
        "fields": {
            "irsaliye_no": ("code", "IR-2026-6621"),
            "gonderen": ("name", "Ege Kâğıt Ürünleri San. Ltd."),
            "alici": ("name", "Ünal Kırtasiye Depo"),
            "kalem_sayisi": ("int", 4),
            "plaka": ("plate", "35 GKT 412"),
        },
        "lines": [
            "SEVK İRSALİYESİ   (tedarik)",
            "İrsaliye No : {irsaliye_no}",
            "Gönderen : {gonderen} (Manisa)",
            "Alıcı    : {alici} - İzmir/Bornova",
            "Kalemler :",
            "  A4 fotokopi kağıdı 500y x30 koli",
            "  Klasör (mavi) x120",
            "  Zarf 90gr x50 paket",
            "  Not defteri A5 x200",
            "Kalem sayısı: {kalem_sayisi}",
            "Şoför: M. GÜRSOY   Araç plakası: {plaka}",
            "Sevk tarihi: 17.10.2026 (tahmini teslim)",
        ],
    },
    {
        "slug": "ocr-siparis",
        "difficulty": 3,
        "check": {"type": "json_fields", "strict": True},
        "fields": {
            "musteri": ("name", "Sertaç Yıldır"),
            "siparis_no": ("code", "SP-44071"),
            "odeme_turu": ("code", "HAVALE/EFT"),
            "tutar": ("money", 899.75),
            "teslim_sehir": ("name", "İzmir"),
        },
        "lines": [
            "*** SİPARİŞ ÖZETİ (sanal mağaza) ***",
            "Müşteri  : {musteri} (sertac@example-mail.com)",
            "Sipariş No: {siparis_no}",
            "Kalem    : 1x kamp çadırı 2 kişilik - 749,85 TL",
            "           1x uyku tulumu            - 149,90 TL",
            "Kargo    : ücretsiz (>500 TL kampanyası)",
            "Ödeme    : {odeme_turu}",
            "-----------------------------------------------",
            "TOPLAM   : {tutar}",
            "Teslimat : {teslim_sehir} - Bayraklı",
            "Not: kargo çıkışı Cuma günü planlandı.",
        ],
    },
    {
        "slug": "ocr-recete",
        "difficulty": 4,
        "check": {
            "type": "json_fields",
            "required": ["doktor", "tarih", "ilac_sayisi"],
        },
        "fields": {
            "doktor": ("name", "Hale Soylu"),
            "hasta": ("name", "Necdet Arman"),
            "tarih": ("date", "2026-10-17"),
            "ilac_sayisi": ("int", 4),
            "teshis": ("text", "akut farenjit"),
        },
        "lines": [
            "AİLE HEKİMLİĞİ REÇETESİ",
            "Dr. {doktor}   Aile Hekimi (birim 2)",
            "Hasta: {hasta}    Protokol: 2026/88412",
            "Tarih: {tarih}",
            "Rp/ 1. Amoksisilin 1000mg tb 2x1",
            "    2. Parasetamol 500mg tb 3x1",
            "    3. Boğaz spreyi 30ml 3x2",
            "    4. D vitamini damla 1x7",
            "Teşhis: {teshis}",
            "Not: bol sıvı, sigara yasak. Kontrol 1 hafta.",
        ],
    },
    {
        "slug": "ocr-uyelik",
        "difficulty": 3,
        "check": {"type": "json_fields", "strict": True},
        "fields": {
            "uye_adi": ("name", "Fidan Özgür"),
            "uye_no": ("code", "UY-33820"),
            "baslangic": ("date", "2026-10-12"),
            "aidat": ("money", 750.00),
            "telefon": ("code", "0532 614 88 02"),
        },
        "lines": [
            "SPOR SALONU ÜYELİK FORMU (fotokopi)",
            "Ad soyad : {uye_adi}",
            "Üye no   : {uye_no}",
            "Başlangıç: {baslangic} (12 ay taahhüt)",
            "Aylık aidat: {aidat}",
            "Telefon  : {telefon}",
            "Acil durum: annesi - 0533 207 41 66",
            "İmza: ____  Yetkili: D. ALGAN",
        ],
    },
    {
        "slug": "ocr-gider-nota",
        "difficulty": 4,
        "check": {"type": "json_fields", "strict": True},
        "fields": {
            "belge_no": ("code", "GN-2026/0903"),
            "tarih": ("date", "2026-10-18"),
            "unvan": ("name", "Pars Çevre Temizlik Hizmetleri"),
            "aciklama": ("code", "EKİM"),
            "tutar": ("money", 1575.00),
        },
        "lines": [
            "GİDER MAKBUZU / NOTA",
            "Belge no : {belge_no}",
            "Tarih    : {tarih}",
            "Ödeyen   : Site Yönetimi - Menekşe Sitesi",
            "Alan     : {unvan}",
            "Açıklama : {aciklama} ayı ortak alan temizliği",
            "Tutar    : {tutar} TL (KDV dahil, elden)",
            "Kaşe/imza: var (okunamayan bölge)",
        ],
    },
    {
        "slug": "ocr-kira-sozlesme",
        "difficulty": 4,
        "check": {"type": "json_fields", "strict": True},
        "fields": {
            "kiraci": ("name", "Elif Sarıkaya"),
            "malik": ("name", "Orhan Demirtaş"),
            "daire_adresi": ("text", "Cemil Topuzlu Cad. No:23 D:5 Göztepe/İSTANBUL"),
            "baslangic": ("date", "2026-11-01"),
            "aylik_kira": ("money", 27500.00),
            "depozito": ("money", 55000.00),
        },
        "lines": [
            "KONUT KİRA SÖZLEŞMESİ (fotokopi nüsha)",
            "Kiraya veren (malik): {malik}   TCKN: *** *** **21",
            "Kiracı            : {kiraci}",
            "Kiralanan         : {daire_adresi}",
            "Sözleşme süresi   : 1 (bir) yıl",
            "Başlangıç tarihi  : {baslangic}",
            "Aylık kira bedeli : {aylik_kira} (her ayın 5'ine kadar)",
            "Depozito          : {depozito} — elden teslim alındı",
            "Düzenleme tarihi  : 20.10.2026",
            "İmza: malik ___ / kiracı ___   Şahit: M. ERCAN",
        ],
    },
    {
        "slug": "ocr-kargo-etiket",
        "difficulty": 3,
        "check": {"type": "json_fields", "strict": True},
        "fields": {
            "gonderi_no": ("code", "YZK-8821-4607"),
            "alici": ("name", "Nurgül Aksoy"),
            "sehir": ("name", "Trabzon"),
            "agirlik_kg": ("num", 2.4),
            "odeme_tipi": ("code", "KAPIDA_ODEME"),
        },
        "lines": [
            "ANADOLU KARGO - GÖNDERİ ETİKETİ",
            "Gönderi No : {gonderi_no}    Takip: yzk.co/g/{gonderi_no}",
            "Alıcı      : {alici}",
            "Adres      : Ortahisar Mah. Uzun Sk. No:8 {sehir}",
            "Gönderen   : Şen Pazarlama - İstanbul/Avcılar",
            "Ağırlık    : {agirlik_kg} kg   Desi: 3,1",
            "Ödeme tipi : {odeme_tipi} (tahsilatlı 184,90 TL)",
            "Barkod     : ||| {gonderi_no} |||",
            "Uyarı      : kırılabilir - bu yüzey üste gelecek",
        ],
    },
    {
        "slug": "ocr-lab-sonuc",
        "difficulty": 5,
        "check": {
            "type": "json_fields",
            "required": ["hasta", "tarih", "hgb"],
        },
        "fields": {
            "hasta": ("name", "Veysel Karaca"),
            "tarih": ("date", "2026-10-14"),
            "hgb": ("num", 14.2),
            "hct": ("num", 42.8),
            "plt": ("int", 241),
            "wbc": ("num", 7.3),
        },
        "lines": [
            "ŞEHİR HASTANESİ - HEMATOLOJİ LABORATUVAR SONUCU",
            "Barkod: LAB-2026-7741     Protokol: H-99120",
            "Hasta: {hasta}   (erkek, 54)",
            "Örnek alım: 08:35    Kabul: 09:10",
            "Rapor tarihi: {tarih}",
            "TEST            SONUÇ    BİRİM     REFERANS",
            "WBC             {wbc}    10e3/uL   4,0-10,0",
            "HGB             {hgb}    g/dL      12,0-16,0",
            "HCT             {hct}    %         37,0-47,0",
            "PLT             {plt}    10e3/uL   150-400",
            "LYM%            28,4     %         20-40",
            "Onay: Uzm. Dr. E. TUNA — elektronik imza",
        ],
    },
]


def _q(v) -> str:
    """YAML-safe scalar quoting (JSON strings are valid YAML)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return json.dumps(str(v), ensure_ascii=False)


def _fold(text: str, indent: int, width: int = 76) -> list[str]:
    pad = " " * indent
    return [
        pad + ln for ln in textwrap.wrap(text, width=width - indent)
    ]


def _check_lines(check: dict) -> list[str]:
    out = [f"      - type: {check['type']}"]
    for k, v in check.items():
        if k == "type":
            continue
        if isinstance(v, list):
            out.append(f"        {k}: [{', '.join(_q(x) for x in v)}]")
        elif isinstance(v, bool):
            out.append(f"        {k}: {'true' if v else 'false'}")
        else:
            out.append(f"        {k}: {_q(v)}")
    return out


def build() -> str:
    chunks = [
        "# Çıkartım/OCR — synthetic OCR-noised extraction tasks.",
        "# GENERATED FILE — do not edit by hand. Rebuild with",
        "# `python3 scripts/gen_ocr_tasks.py` (see --check).",
        "# Field values stay canonical; noise hits labels, layout and",
        "# distractors only. All documents are fictional.",
        "items:",
    ]
    for tpl in TEMPLATES:
        input_text, expected = render_document(
            tpl["fields"], tpl["lines"], seed=tpl["slug"] + "-v1"
        )
        tid = f"cikartim/{tpl['slug']}"
        checks = [tpl["check"],
                  {"type": "not_contains",
                   "terms": ["açıklama", "not:"]}]
        chunks.append(f"  - id: {tid}")
        chunks.append("    category: cikartim")
        chunks.append(f"    difficulty: {tpl['difficulty']}")
        alist = ", ".join(expected.keys())
        chunks.append("    prompt: >-")
        chunks += _fold(PROMPT.format(alist=alist), 6)
        chunks.append("    input: |")
        for ln in input_text.rstrip("\n").splitlines():
            chunks.append("      " + ln if ln else "")
        chunks.append("    expected:")
        for k, v in expected.items():
            chunks.append(f"      {k}: {_q(v)}")
        chunks.append("    checks:")
        for c in checks:
            chunks += _check_lines(c)
        chunks.append("    notes: >-")
        chunks += _fold(
            "synthetic OCR-noised document; regenerate via "
            "scripts/gen_ocr_tasks.py (seed "
            f"{tpl['slug']}-v1)",
            6,
        )
        chunks.append("")
    return "\n".join(chunks) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stdout", action="store_true",
                    help="print instead of writing the dataset file")
    ap.add_argument("--check", action="store_true",
                    help="verify the committed file is up to date")
    args = ap.parse_args()
    text = build()
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(f"stale: {OUT} — run scripts/gen_ocr_tasks.py",
                  file=sys.stderr)
            return 1
        print(f"OK: {OUT} is up to date")
        return 0
    if args.stdout:
        sys.stdout.write(text)
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
