# VNPAY Crawl & Analysis

Thu thap va phan tich review ung dung VNPAY tren Google Play.

## Tep duoc dua len repo
- crawl_vnpay_reviews.py: Script crawl review tu Google Play.
- analyze_reviews.py: Pipeline cleaning + profiling + analysis.
- analysis_report.md: Bao cao tong hop ket qua phan tich.
- vnpay_dashboard.html: Dashboard trinh bay KPI/xu huong.
- vnpay_reviews_cleaned.csv: Du lieu da lam sach de tai hien dashboard va bao cao.
- extracted_samples.json: Mau review trich xuat phuc vu tham khao nhanh.
- VNPAY_logo.png: Tai nguyen hinh anh cho dashboard.

## Tep giu local (khong push)
- .venv/, *.log, cleaning_log.jsonl
- vnpay_reviews_gstore_*.csv (du lieu raw)
- _csv_gz_b64.txt, _logo_b64.txt (artefact trung gian)

## Cai dat nhanh
Yeu cau Python 3.10+.

```bash
pip install pandas numpy
```

## Cach chay
1. Crawl du lieu moi:
```bash
python crawl_vnpay_reviews.py
```

2. Phan tich va sinh bao cao:
```bash
python analyze_reviews.py --input vnpay_reviews_gstore_YYYYMMDD_HHMMSS.csv
```

Neu bo qua --input, script se tu chon file raw moi nhat co mau ten vnpay_reviews_gstore_*.csv.

3. Mo dashboard:
Mo file vnpay_dashboard.html tren trinh duyet.

## Ghi chu
- Dashboard doc truc tiep file vnpay_reviews_cleaned.csv trong cung thu muc.
- Trong moi lan cap nhat du lieu, chi can chay lai analyze_reviews.py de cap nhat report va CSV cleaned.
