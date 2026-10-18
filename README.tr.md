# turkce-ai-karnesi

Türkçe'de gerçekten iş gören LLM'leri ölçen bir değerlendirme kiti — özellikle
insanların fiilen kullandığı ucuz/ücretsiz modeller için.

61 özgün görev (veri seti v1, CC-BY-4.0) 8 kategoride: resmi yazı/dilekçe,
e-posta, özet, dağınık belgeden alan çıkartımı (fatura/tutanak), imla kuralları
(de/da, ki, soru eki), yönerge takibi, TR↔EN çeviri, akıl yürütme.

## Hızlı başlangıç

```bash
pip install -e .
export KARNE_BASE_URL=...   # OpenAI-uyumlu herhangi bir uç
export KARNE_API_KEY=...
export KARNE_MODEL=...

karne run --model $KARNE_MODEL --html
```

Sonuç: `results/` altında JSON + statik HTML karnesi (kategori bazlı grafik
dahil). Her görev deterministik kontrollerle (içerme, satır yapısı, JSON
alan doğruluğu, kelime/cümle sayısı, Türkçe oranı, `spelling_rules` ile
TDK imla taraması) puanlanır — aynı uç + aynı veri seti = aynı puan.

İsteğe bağlı ikinci bir model sabit bir rubrikle jüri olabilir:
`karne run --model X --judge-model Y` (ağırlık `--judge-weight`, varsayılan
0,4; `--judge-runs N` ile her çıktı N kez puanlanıp ölçüt bazında medyan
alınır — tek puanlık sapmayı azaltır). İki koşuyu karşılaştırmak için:
`karne compare a.json b.json` — görev bazında fark, iyileşme/gerileme ve
McNemar anlamlılık testi; `--checks` kontrol bazında geçme/kalma
değişimlerini de listeler.
İstem stili değiştirilebilir: `--prompt-style zero|fewshot|cot`.

Detaylar ve veri seti şeması için: [`README.md`](README.md)
