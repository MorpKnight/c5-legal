# Larger candidate-corpus RAG benchmark

> This benchmark is a behavioral comparison. The local legal corpus is a candidate retrieval corpus, not a verified official authority.

- Mode: `full`
- Cases: `125` (100 covered + 25 missing-context)
- Candidate pair coverage in QA test: `0.28011`
- Indexed chunks for selected covered pairs: `121`
- Selected pairs with multiple distinct titles: `7`

## Aggregate diagnostics

| Condition | F1 all | F1 covered | F1 missing | Grounded precision | Missing-context abstention |
|---|---:|---:|---:|---:|---:|
| adapter_no_rag | 0.39704 | 0.378115 | 0.472744 | None | 0.0 |
| adapter_with_candidate_rag | 0.45679 | 0.53924 | 0.126989 | 0.741647 | 0.76 |

## Paired covered-case comparison

- RAG F1 wins: `65`
- No-RAG F1 wins: `35`
- Ties: `0`
- Mean RAG minus no-RAG F1: `0.161125`

## Selected examples

### qa-covered-0085 (delta F1 `0.980392`)

**Pertanyaan:** Berikan bunyi asli dari Pasal 26 menurut Peraturan Pemerintah Republik Indonesia No 72 Tahun 2009!

**No RAG:** ayat (1) huruf a, huruf b, huruf c, huruf d, huruf e, huruf f, huruf g, huruf h, huruf i, huruf j, huruf k, huruf l, huruf m, huruf n, huruf o, huruf p, huruf q, huruf r, huruf s, huruf t, huruf u, huruf v, huruf w, huruf x, huruf y, huruf z, huruf aa, huruf ab, huruf ac, huruf ad, huruf ae, huruf af, huruf ag, huruf ah, huruf ai, huruf aj, huruf ak, huruf al, huruf am, huruf an, huruf ao, huruf ap, huruf aq, huruf ar, huruf as, huruf at, huruf au, huruf av, huruf aw, huruf ax, huruf ay, huruf az, huruf ba, huruf bb, huruf bc, huruf bd, huruf be, huruf bf, huruf bg, huruf bh, huruf bi, huruf bj, huruf bk, huruf bl, huruf bm, huruf bn, huruf bo, huruf bp, huruf bq, huruf br, huruf bs, huruf bt, huruf bu, huruf bv, huruf bw, huruf bx, huruf by, huruf bz, huruf ca, huruf cb, huruf cc, huruf cd, huruf ce, huruf cf

**Candidate RAG:** (1) Penyelenggara sarana perkeretaapian harus mengumumkan jadwal perjalanan kereta api yang termuat dalam Gapeka kepada masyarakat. (2) Pengumuman sebagaimana dimaksud pada ayat (1) dilaksanakan melalui media massa dan ditempel di stasiun, sebelum pemberlakuan Gapeka.

### qa-covered-0020 (delta F1 `0.728615`)

**Pertanyaan:** Sebutkan semua ketentuan yang ada dalam Pasal 12 dari Undang-Undang Republik Indonesia No 20 Tahun 2003!

**No RAG:** Redaksional Pasal dalam Pasal 12 dalam Undang-Undang Republik Indonesia No 20 Tahun 2003 tentang Sistem Jaminan Sosial Nasional:
Cukup jelas

**Candidate RAG:** Berdasarkan konteks yang diberikan, Pasal 12 dalam UNDANG-UNDANG Nomor 20 Tahun 2003 tentang SISTEM PENDIDIKAN NASIONAL:
(1) Setiap peserta didik pada setiap satuan pendidikan berhak : a. mendapatkan pendidikan agama sesuai dengan agama yang dianutnya dan diajarkan oleh pendidik yang seagama; b. mendapatkan pelayanan pendidikan sesuai dengan bakat, minat, dan kemampuannya; c. mendapatkan beasiswa bagi yang berprestasi yang orang tuanya tidak mampu membiayai pendidikannya; d. mendapatkan biaya pendidikan bagi mereka yang orang tuanya tidak mampu membiayai pendidikannya; e. pindah ke program pendidikan pada jalur dan satuan pendidikan lain yang setara; f. menyelesaikan program pendidikan sesuai dengan kecepatan belajar masing-masing dan tidak menyimpang dari ketentuan batas waktu yang ditetapkan. (2) Setiap peserta didik berkewajiban : a. menjaga norma-norma pendidikan untuk menjamin keberlangsungan proses dan keberhasilan pendidikan; b. ikut menanggung biaya penyelenggaraan pendidikan, kecuali bagi peserta didik yang dibebaskan dari kewajiban tersebut sesuai dengan peraturan perundang-undangan yang berlaku. (3) Warga negara asing dapat menjadi peserta didik pada satuan pendidikan yang diselenggarakan dalam wilayah Negara Kesatuan Republik Indonesia. (4

### qa-covered-0036 (delta F1 `0.721804`)

**Pertanyaan:** Berikan isi dokumen dari Pasal 6 dalam Keputusan Presiden Republik Indonesia No 43 Tahun 1990!

**No RAG:** Isi dokumen dari Pasal 6 dalam Keputusan Presiden Republik Indonesia No 43 Tahun 1990 tentang Pengesahan Persetujuan Antara Pemerintah Republik:
, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62,

**Candidate RAG:** Teks Pasal berdasarkan Pasal 6 dalam Keputusan Presiden Republik Indonesia No 43 Tahun 1990 tentang Badan Koordinasi Nasional Penanggulangan Bencana:
- (1) Bupati/Walikotamadya Kepala Daerah Tingkat II memimpin Satuan Pelaksana Penanggulangan Bencana, selanjutnya disingkat Satlak Penanggulangan Bencana. - (2) Satlak Penanggulangan Bencana bertanggung jawab langsung kepada Ketua Bakornas Penanggulangan Bencana melalui Gubernur Kepala Daerah Tingkat I yang bersangkutan.

### qa-covered-0063 (delta F1 `0.695765`)

**Pertanyaan:** Apa bunyi dari Pasal 17 menurut Keputusan Presiden Republik Indonesia No 52 Tahun 2001?

**No RAG:** (1) Dalam melaksanakan tugasnya, Deputi dibantu oleh Sekretariat Deputi. (2) Sekretariat Deputi dipimpin oleh seorang Sekretaris Deputi.

**Candidate RAG:** Pasal 17 dalam Keputusan Presiden Republik Indonesia No 52 Tahun 2001 tentang Perubahan Atas Keputusan Presiden Nomor 117 Tahun 2000 Tentang Sekretariat Negara:
"Pasal 17 - (1) Deputi adalah jabatan eselon Ia. - (2) Staf Ahli adalah jabatan eselon Ib. - (3) Kepala Pusat dan Kepala Biro adalah jabatan eselon IIa. - (4) Kepala Bidang dan Kepala Bagian adalah jabatan eselon IIIa. - (5) Kepala Unit adalah jabatan setinggi-tingginya eselon IIIa. - (6) Kepala Subbagian adalah jabatan eselon IVa."

### qa-covered-0053 (delta F1 `0.695514`)

**Pertanyaan:** Tulis isi hukum dari Pasal 1 dalam Keputusan Presiden Republik Indonesia No 3 Tahun 1999!

**No RAG:** Isi hukum dari Pasal 1 dalam Keputusan Presiden Republik Indonesia No 3 Tahun 1999 tentang Pengesahan Persetujuan Antara Pemerintah Republik:
Mengesahkan Persetujuan antara Pemerintah Republik Indonesia dan Pemerintah Republik Rakyat Tiongkok mengenai Penghindaran Pajak Berganda dan Pencegahan Pengelakan Pajak atas Penghasilan (Agreement between the Government of the Republic of Indonesia and the Government of the People's Republic of China on the Avoidance of Double Taxation and the Prevention of Fiscal Evasion with Respect to Taxes on Income) yang telah ditandatangani Pemerintah Republik Indonesia di Jakarta pada tanggal 20 Desember 1997 sebagai hasil perundingan antara Delegasi -delegasi Pemerintah Republik Indonesia dan Pemerintah Republik Rakyat Tiongkok yang salinan naskah aslinya dalam bahasa Indonesia, bahasa Mandarin dan bahasa Inggris sebagaimana terlampir pada Keputusan Presiden ini.

**Candidate RAG:** Isi hukum dari Pasal 1 dalam Keputusan Presiden Republik Indonesia No 3 Tahun 1999 tentang Pernyataan Persetujuan Atas Kenaikan Kuota Republik Indonesia Pada Dana Moneter Internasional:
Menyetujui kenaikan kuota Republik Indonesia pada Dana Moneter Internasional dari SDR 1.497.600.000,00 (satu miliar empat ratus sembilan puluh tujuh juta enam ratus ribu special drawing rights ) menjadi SDR 2.079.300.000,00 (dua miliar tujuh puluh sembilan juta tiga ratus ribu special drawing rights ) sebagaimana telah diputuskan oleh Dewan Gubernur Dana Moneter Internasional pada tanggal 30 Januari 1998 melalui Resolusi No. 53-2 tentang Increase in Quotas of Fund members-Eleventh General Review.

### qa-covered-0096 (delta F1 `-0.44831`)

**Pertanyaan:** Berikan isi dokumen dari Pasal 152 dalam Peraturan Pemerintah Republik Indonesia No 72 Tahun 2009!

**No RAG:** Isi dokumen dari Pasal 152 dalam Peraturan Pemerintah Republik Indonesia No 72 Tahun 2009 tentang Jenis Dan Tarif Atas Jenis Penerimaan Negara Bukan Pajak:
Cukup jelas.

**Candidate RAG:** [NO_CONTEXT]

### qa-covered-0068 (delta F1 `-0.495369`)

**Pertanyaan:** Tulis isi hukum dari Pasal 43 dalam Peraturan Presiden Republik Indonesia No 19 Tahun 2016!

**No RAG:** Isi hukum dari Pasal 43 dalam Peraturan Presiden Republik Indonesia No 19 Tahun 2016 tentang Perubahan Atas Peraturan Presiden Nomor 10 Tahun 2010 Tentang:
diubah sehingga berbunyi sebagai berikut:

**Candidate RAG:** Isi hukum dari Pasal 43 dalam Peraturan Presiden Republik Indonesia No 19 Tahun 2016 tentang Perubahan Kedua Atas Peraturan Presiden Nomor 12 Tahun 2013 Tentang Jaminan Kesehatan:
(1) BPJS Kesehatan mengembangkan teknis operasionalisasi sistem pelayanan kesehatan, sistem kendali mutu pelayanan, dan sistem pembayaran pelayanan kesehatan untuk meningkatkan efisiensi dan efektivitas. (2) Pengembangan sebagaimana dimaksud pada ayat (1) dilaksanakan dalam rangka penyelenggaraan program Jaminan Kesehatan. (3) Dalam melaksanakan pengembangan sebagaimana dimaksud pada ayat (1), BPJS Kesehatan berkoordinasi dengan kementerian/lembaga terkait.

### qa-covered-0033 (delta F1 `-0.533412`)

**Pertanyaan:** Apa saja poin yang tercantum dalam Pasal 4 dalam Undang-Undang Republik Indonesia No 3 Tahun 2008?

**No RAG:** Berikut kutipan verbatim dari Pasal 4 dalam Undang-Undang Republik Indonesia No 3 Tahun 2008 tentang Pembentukan Kabupaten Padang Lawas Utara:
Cukup jelas.

**Candidate RAG:** Poin yang tercantum dalam Pasal 4 dalam Undang-Undang Republik Indonesia No 3 Tahun 2008 tentang Perubahan Atas Undang-Undang Nomor 15 Tahun 1997 Tentang Ketenagalistrikan:
ayat (1) huruf a, huruf b, huruf c, huruf d, huruf e, huruf f, huruf g, huruf h, huruf i, huruf j, huruf k, huruf 1, huruf m, huruf n, huruf o, huruf p, huruf q, huruf r, huruf s, huruf t, huruf u, huruf v, huruf w, huruf x, huruf y, huruf z, huruf aa, huruf ab, huruf ac, huruf ad, huruf ae, huruf af, huruf ag, huruf ah, huruf ai, huruf aj, huruf ak, huruf al, huruf am, huruf an, huruf ao, huruf ap, huruf aq, huruf ar, huruf as, huruf at, huruf au, huruf av, huruf aw, huruf ax, huruf ay, huruf az, huruf ba, huruf bb, huruf bc, huruf bd, huruf be, huruf bf, huruf bg, huruf bh, huruf bi, huruf bj, huruf bk, huruf bl, huruf bm, huruf bn, huruf bo

### qa-covered-0100 (delta F1 `-0.654006`)

**Pertanyaan:** Apa yang tertulis dalam Pasal 21 dalam Peraturan Pemerintah Republik Indonesia No 32 Tahun 2011?

**No RAG:** Tertulis dalam Pasal 21 dalam Peraturan Pemerintah Republik Indonesia No 32 Tahun 2011 tentang Pelayanan Meteo Rologi, Klimatologi, Dan Geofi Sika:
Cukup jelas.

**Candidate RAG:** Berdasarkan konteks yang diberikan, Pasal 21 dalam Peraturan Pemerintah Republik Indonesia No 32 Tahun 2011 tentang Pelayanan Darah:
ayat (1) huruf a, dilakukan oleh: a. menteri yang bertanggung jawab di bidang sarana dan prasarana lalu lintas dan angkutan jalan melalui penetapan rencana kebijakan lalu lintas yang berlaku pada setiap ruas jalan dan/atau persimpangan di jalan nasional; b. menteri yang bertanggung jawab di bidang jalan, meliputi penetapan rencana kebijakan pengaturan penggunaan jaringan jalan dan gerakan lalu lintas melalui penetapan kelas jalan nasional; dan c. gubernur, meliputi penetapan rencana kebijakan pengaturan penggunaan jaringan jalan dan gerakan lalu lintas melalui penetapan kelas jalan provinsi. (2) Penetapan rencana kebijakan pengaturan penggunaan jaringan jalan dan gerakan lalu lintas sebagaimana dimaksud pada ayat (1) dilakukan dengan memperhatikan: a. rencana induk jaringan jalan; b. rencana induk gerakan lalu lintas; c. rencana induk jaringan jalan dan rencana induk gerakan lalu lintas; dan d. rencana induk jaringan jalan dan rencana induk gerakan lalu lintas. (3) Penetapan rencana kebijakan pengaturan penggunaan jaringan jalan dan gerakan lalu lintas sebagaimana dimaksud pada ayat (1) dilakukan dengan memperhatikan: a. rencana induk jaringan jalan; b. rencana induk gerakan lalu lintas; c. rencana induk jaringan jalan dan rencana induk gerakan lalu lintas;

### qa-covered-0079 (delta F1 `-0.818919`)

**Pertanyaan:** Tulis isi hukum dari Pasal 23 dalam Undang-Undang Republik Indonesia No 44 Tahun 2008!

**No RAG:** Isi hukum dari Pasal 23 dalam Undang-Undang Republik Indonesia No 44 Tahun 2008 tentang Rumah Sakit:
Cukup jelas.

**Candidate RAG:** [NO_CONTEXT]

## Limitations

- QA completions and the candidate corpus may have truncation, OCR noise, or dataset-level overlap.
- A retrieval hit in this benchmark means an exact local regulation/article metadata match; it does not establish official provenance or legal currentness.
- Multiple titles under one regulation/article key indicate that the current key is not sufficient for production retrieval; issuer, canonical title, source URL, or another document identity must also be indexed.
- Token-F1, grounding precision, and abstention heuristics are diagnostics. Human legal review remains required.
