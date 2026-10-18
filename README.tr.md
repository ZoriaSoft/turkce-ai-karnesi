# turkce-ai-karnesi

Türkçe'de gerçekten iş gören LLM'leri ölçen bir değerlendirme kiti — özellikle
insanların fiilen kullandığı ucuz/ücretsiz modeller için.

27 özgün görev (veri seti v1, CC-BY-4.0) 8 kategoride: resmi yazı/dilekçe,
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

Sonuç: `results/` altında JSON + statik HTML karnesi. Her görev deterministik
kontrollerle (içerme, satır yapısı, JSON alan doğruluğu, kelime/cümle sayısı,
Türkçe oranı) puanlanır — aynı uç + aynı veri seti = aynı puan.

Detaylar ve veri seti şeması için: [`README.md`](README.md)
