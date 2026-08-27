# P0.3 Pilot Selection

## Outcome

Selector deterministik menghasilkan 50 istilah untuk review. Pilot ini belum merupakan gold set: seluruh record masih berstatus `pending_review`, dan tidak ada label retrieval yang dibuat pada P0.3.

## Input boundary

- Input corpus: `data/interim/legal_term_senses.parquet`
- Input SHA-256: `bacda8b890a6beb512fe93a571f5343a0817d9a92b29802b373083d8740d4282`
- Eligible terms after excluding normalization warnings: 3,118
- Normalization-warning terms routed to review queue: 13
- Quarantined terms routed to review queue: 15
- Target pilot: 50
- Maximum selected terms per primary source: 3

## Selection buckets

- `anchor`: 10
- `multi_sense`: 2
- `domain_focus`: 10
- `near_neighbor`: 8
- `alias`: 6
- `numeric`: 4
- `long_definition`: 5
- `typical_fill`: 5

## Primary regulation types

- `Undang-Undang`: 28
- `Peraturan Menteri Perhubungan`: 4
- `Peraturan Pemerintah`: 3
- `Peraturan Lembaga Penjamin Simpanan`: 2
- `Peraturan Menteri Pemberdayaan Perempuan dan Perlindungan Anak`: 2
- `Peraturan Menteri Perdagangan`: 2
- `Peraturan Otoritas Jasa Keuangan`: 2
- `Peraturan Bank Indonesia`: 1
- `Peraturan Mahkamah Agung`: 1
- `Peraturan Menteri Kelautan dan Perikanan`: 1
- `Peraturan Menteri Keuangan`: 1
- `Peraturan Menteri Komunikasi dan Informatika`: 1
- `Peraturan Menteri Perindustrian`: 1
- `Peraturan Presiden`: 1

## Diversity checks

- Unique selected term IDs: 50
- Unique primary sources: 39
- Maximum observed terms from one primary source: 3
- Terms with multiple senses: 2
- Terms containing aliases: 11
- Terms containing digits: 7
- Near-neighbor terms: 8
- Selection seed: `c5-p0.3-v1`

## Selected terms

1. **Badan Usaha** — `anchor` — Undang-Undang Nomor 11 Tahun 2020
2. **Data Pribadi** — `anchor` — Undang-Undang Nomor 27 Tahun 2022
3. **Dewan Komisaris** — `anchor` — Undang-Undang Nomor 40 Tahun 2007
4. **Direksi** — `anchor` — Undang-Undang Nomor 40 Tahun 2007
5. **Hukum Adat** — `anchor` — Undang-Undang Nomor 21 Tahun 2001
6. **Jaminan Fidusia** — `anchor` — Undang-Undang Nomor 42 Tahun 1999
7. **Konsumen** — `anchor` — Undang-Undang Nomor 8 Tahun 1999
8. **Masyarakat Hukum Adat** — `anchor` — Undang-Undang Nomor 32 Tahun 2009
9. **Pengendali Data Pribadi** — `anchor` — Undang-Undang Nomor 27 Tahun 2022
10. **Perseroan Terbatas** — `anchor` — Undang-Undang Nomor 40 Tahun 2007
11. **Kode Etik Jurnalistik** — `multi_sense` — Peraturan Presiden Nomor 32 Tahun 2024
12. **Lembaga Penyedia Layanan Peningkatan Kualitas Keluarga** — `multi_sense` — Peraturan Menteri Pemberdayaan Perempuan dan Perlindungan Anak Nomor 3 Tahun 2023
13. **Dokumen Elektronik** — `domain_focus` — Undang-Undang Nomor 19 Tahun 2016
14. **Informasi Elektronik** — `domain_focus` — Undang-Undang Nomor 19 Tahun 2016
15. **Kesejahteraan Pekerja/Buruh** — `domain_focus` — Undang-Undang Nomor 13 Tahun 2003
16. **Kontrak Kerja Konstruksi** — `domain_focus` — Undang-Undang Nomor 2 Tahun 2017
17. **Korporasi** — `domain_focus` — Undang-Undang Nomor 9 Tahun 2013
18. **Nasabah Debitur** — `domain_focus` — Undang-Undang Nomor 10 Tahun 1998
19. **Pelaku Usaha Sektor Keuangan** — `domain_focus` — Undang-Undang Nomor 4 Tahun 2023
20. **Perjanjian Internasional** — `domain_focus` — Undang-Undang Nomor 24 Tahun 2000
21. **Prosesor Data Pribadi** — `domain_focus` — Undang-Undang Nomor 27 Tahun 2022
22. **Tanda Tangan Elektronik** — `domain_focus` — Undang-Undang Nomor 19 Tahun 2016
23. **Bahan Kimia Daftar 1** — `near_neighbor` — Undang-Undang Nomor 9 Tahun 2008
24. **Bahan Kimia Daftar 3** — `near_neighbor` — Undang-Undang Nomor 9 Tahun 2008
25. **Bank dalam Likuidasi** — `near_neighbor` — Peraturan Lembaga Penjamin Simpanan Nomor 1 Tahun 2022
26. **Bebas dari Tera dan Tera Ulang** — `near_neighbor` — Peraturan Menteri Perdagangan Nomor 24 Tahun 2024
27. **Bebas dari Tera Ulang** — `near_neighbor` — Peraturan Menteri Perdagangan Nomor 24 Tahun 2024
28. **Kapal Penumpang di Bawah Permukaan Air (Passenger Submersible Craft)** — `near_neighbor` — Peraturan Menteri Perhubungan Nomor PM 6 Tahun 2022
29. **Kelaiklautan Kapal Penumpang di Bawah Permukaan Air (Passenger Submersible Craft)** — `near_neighbor` — Peraturan Menteri Perhubungan Nomor PM 6 Tahun 2022
30. **Likuidasi Bank** — `near_neighbor` — Peraturan Lembaga Penjamin Simpanan Nomor 1 Tahun 2022
31. **Benih Bening Lobster (puerulus)** — `alias` — Peraturan Menteri Kelautan dan Perikanan Nomor 7 Tahun 2024
32. **Dana Reboisasi** — `alias` — Peraturan Pemerintah Nomor 23 Tahun 2021
33. **Factoring With Recourse** — `alias` — Peraturan Otoritas Jasa Keuangan Nomor 35/POJK.05/2018
34. **Klien Pemasyarakatan** — `alias` — Undang-Undang Nomor 22 Tahun 2022
35. **Manual Operasi Penyelenggara Perancangan Prosedur Penerbangan** — `alias` — Peraturan Menteri Perhubungan Nomor PM 11 Tahun 2022
36. **Pernyataan Standar Akuntansi Pemerintahan** — `alias` — Peraturan Pemerintah Nomor 71 Tahun 2010
37. **Air Minum pH Tinggi** — `numeric` — Peraturan Menteri Perindustrian Nomor 62 Tahun 2024
38. **Entitas Induk yang Dimiliki Sebagian (Partially-Owned Parent Entity)** — `numeric` — Peraturan Menteri Keuangan Nomor 136 Tahun 2024
39. **Nomor UN (UN Number)** — `numeric` — Peraturan Menteri Perhubungan Nomor PM 32 Tahun 2022
40. **Pengakhiran Transaksi Keuangan melalui Perjumpaan Utang** — `numeric` — Peraturan Bank Indonesia Nomor 12 Tahun 2023
41. **Gender** — `long_definition` — Peraturan Menteri Pemberdayaan Perempuan dan Perlindungan Anak Nomor 13 Tahun 2021
42. **Kosmetik** — `long_definition` — Peraturan Pemerintah Nomor 28 Tahun 2024
43. **Layanan Pengiriman Elektronik Tercatat** — `long_definition` — Peraturan Menteri Komunikasi dan Informatika Nomor 11 Tahun 2022
44. **Musyawarah Penetapan Ganti Kerugian** — `long_definition` — Peraturan Mahkamah Agung Nomor 2 Tahun 2021
45. **Perselisihan Hubungan Industrial** — `long_definition` — Undang-Undang Nomor 2 Tahun 2004
46. **Arsitektur** — `typical_fill` — Undang-Undang Nomor 6 Tahun 2017
47. **Badan Amil Zakat Nasional** — `typical_fill` — Undang-Undang Nomor 23 Tahun 2011
48. **Efek Bersifat Utang Terkait Keberlanjutan (sustainability-linked bond) dan/atau Sukuk Terkait Keberlanjutan (sustainability-linked sukuk)** — `typical_fill` — Peraturan Otoritas Jasa Keuangan Nomor 18 Tahun 2023
49. **Lingkungan Hidup** — `typical_fill` — Undang-Undang Nomor 32 Tahun 2009
50. **Penyelenggaraan Telekomunikasi** — `typical_fill` — Undang-Undang Nomor 36 Tahun 1999

## Review contract

- `pending_review` berarti istilah hanya dipilih untuk eksperimen.
- Reviewer boleh memilih `approve`, `reject`, atau `needs_review`.
- Reviewer tidak mengubah definisi sumber di dalam file pilot.
- Quarantine dan normalization warning tidak masuk 50 istilah utama.
- Source verification, query authoring, dan locked test split adalah tahap terpisah.
