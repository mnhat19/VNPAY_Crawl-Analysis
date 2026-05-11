# Báo cáo phân tích reviews Google Play - VNPAY

- Nguồn dữ liệu: vnpay_reviews_gstore_20260510_102042.csv
- Encoding: utf-8-sig
- Số dòng (raw): 5000
- Số cột: 15

## 1) Data Profiling & Data Quality Assessment

**Tổng quan chất lượng**
- Tỷ lệ review trống/rất ngắn chiếm 11.4%.
- Phát hiện ký tự lỗi mã hóa trong một số trường văn bản.
- Có dấu hiệu outlier ở số lượt like (thumbsUpCount).
- Lưu ý: một số review có nội dung tích cực nhưng xếp 1 sao (nghi là bot/phản ứng sự kiện), cần lọc thủ công khi phân tích sâu.

**Missing values (top 8)**
| Cột | Số missing | Tỷ lệ |
| --- | --- | --- |
| replyContent | 4666 | 93.3% |
| repliedAt | 4666 | 93.3% |
| reviewCreatedVersion | 2199 | 44.0% |
| appVersion | 2199 | 44.0% |
| content_norm | 116 | 2.3% |
| content_fold | 116 | 2.3% |
| reviewId | 0 | 0.0% |
| userName | 0 | 0.0% |

**Trùng lặp**
- Duplicate theo reviewId: 0
- Duplicate theo (content chuẩn hoá, userName, at): 0

**Rating/Datetime**
- Rating không hợp lệ: 0
- Datetime lỗi (at): 0
- Datetime lỗi (repliedAt): 4666

**Outliers & encoding**
- Outlier thumbsUpCount: 749
- Outlier độ dài review: 412
- Ký tự lỗi mã hóa: 2

**Review ngắn vô nghĩa**
- Rỗng/không nội dung: 116
- Ngắn/low-info: 455

**Usability cột**
| Cột | Missing | Unique | Usable |
| --- | --- | --- | --- |
| reviewId | 0.0% | 100.0% | High |
| userName | 0.0% | 93.8% | High |
| userImage | 0.0% | 100.0% | High |
| content | 0.0% | 78.7% | High |
| score | 0.0% | 0.1% | High |
| thumbsUpCount | 0.0% | 1.9% | High |
| reviewCreatedVersion | 44.0% | 1.7% | Low |
| at | 0.0% | 98.3% | High |
| replyContent | 93.3% | 0.7% | Low |
| repliedAt | 93.3% | 6.6% | Low |
| appVersion | 44.0% | 1.7% | Low |
| content_raw | 0.0% | 78.7% | High |
| content_norm | 2.3% | 70.3% | High |
| content_fold | 2.3% | 69.8% | High |
| content_len | 0.0% | 6.4% | Medium |

## 2) Data Cleaning & Preprocessing

**Các bước làm sạch**
- remove_invalid_score: 5000 -> 5000 (0 removed)
- deduplicate: 5000 -> 5000 (0 removed)
- remove_short_or_empty: 5000 -> 4429 (571 removed)

- Output cleaned CSV: vnpay_reviews_cleaned.csv
- Log cleaning: cleaning_log.jsonl

## 3) Business-Focused Review Analysis

**Phân bố rating** _(tính trên 4.429 reviews đã làm sạch)_
| Rating | Số lượng | Tỷ lệ |
| --- | --- | --- |
| 1 | 285 | 6.43% |
| 2 | 16 | 0.36% |
| 3 | 25 | 0.56% |
| 4 | 13 | 0.29% |
| 5 | 4090 | 92.35% |

- **Điểm trung bình: 4.72** (thang 1–5)
- **Tỉ lệ đánh giá ≤4 sao: 7.65%** (339/4.429 reviews)
- **Tỉ lệ có phản hồi từ VNPAY: 6.43%** (285/4.429 reviews)

**Xu hướng theo tháng**
| Tháng | Reviews | Avg rating | Tỷ lệ ≤4 sao | Đã phản hồi |
| --- | --- | --- | --- | --- |
| 2025-05 | 4065 | 4.92 | 2.1% | 41 |
| 2025-06 | 61 | 4.02 | 27.9% | 18 |
| 2025-07 | 42 | 2.40 | 66.7% | 37 |
| 2025-08 | 47 | 2.74 | 66.0% | 45 |
| 2025-09 | 30 | 2.23 | 76.7% | 13 |
| 2025-10 | 35 | 2.20 | 77.1% | 1 |
| 2025-11 | 16 | 1.81 | 81.2% | 16 |
| 2025-12 | 26 | 1.69 | 84.6% | 26 |
| 2026-01 | 24 | 1.88 | 91.7% | 23 |
| 2026-02 | 18 | 1.67 | 83.3% | 18 |
| 2026-03 | 31 | 1.87 | 83.9% | 29 |
| 2026-04 | 22 | 1.73 | 86.4% | 18 |
| 2026-05 | 12 | 2.42 | 75.0% | 0 |

- **Đánh giá trung bình có xu hướng giảm mạnh theo tháng**: từ 4.92 (05/2025) xuống 1.67 (02/2026).
- **Tháng có đột biến review tiêu cực cao nhất**: **2026-01** (91.7% ≤4 sao).
- **Tháng có lượng review tích cực cao nhất**: **2025-05** (97.9% là 5 sao — đây là tháng có lượng review tổng lớn bất thường, nghi liên quan đến sự kiện/chiến dịch marketing).
- Lưu ý: tỉ lệ phản hồi theo tháng dao động lớn (2025-10: 1/35; 2025-12: 26/26=100%) — dữ liệu replyContent từ raw data có thể bị trễ hoặc không đồng đều.

**Cụm từ phổ biến trong review 1–4 sao**
| Cụm từ | Số review | ThumbsUp | Tháng đầu | Tháng cuối |
| --- | --- | --- | --- | --- |
| xác thực | 24 | 513 | 2025-05 | 2026-05 |
| khuôn mặt | 22 | 49 | 2025-05 | 2026-05 |
| ngân hàng | 21 | 65 | 2025-05 | 2026-05 |
| thanh toán | 21 | 278 | 2025-05 | 2026-05 |
| định danh | 21 | 536 | 2025-05 | 2026-05 |
| liên kết | 19 | 50 | 2025-05 | 2026-04 |
| hỗ trợ | 18 | 51 | 2025-05 | 2026-04 |
| tài khoản | 17 | 27 | 2025-05 | 2026-04 |
| không được | 13 | 39 | 2025-05 | 2026-02 |
| cũng không | 13 | 40 | 2025-06 | 2026-04 |
| không có | 14 | 509 | 2025-06 | 2026-04 |
| thành công | 13 | 25 | 2025-05 | 2026-05 |

**Nhóm vấn đề theo từ khóa (trong 339 review 1–4 sao)**
| Nhóm vấn đề | Số review | Tỷ lệ / tổng tiêu cực |
| --- | --- | --- |
| Thanh toán / Ngân hàng / Liên kết | 61 | 18.0% |
| Xác thực / Định danh / Khuôn mặt | 58 | 17.1% |
| Nạp tiền / Trừ tiền / Đặt vé | 38 | 11.2% |
| OTP / Mật khẩu / Đăng nhập | 37 | 10.9% |
| Hỗ trợ / Tổng đài | 32 | 9.4% |
| Ưu đãi / Voucher / Thông báo | 24 | 7.1% |

> Lưu ý: một review có thể thuộc nhiều nhóm. Thứ tự phản ánh tần suất xuất hiện từ khoá, không phải mức độ nghiêm trọng.

**Top bình luận tiêu cực được tán thành (1–2 sao, sort by thumbsUp)**
> (1 sao, 2026-03, 👍 482) app siêu kém xác thực định danh yêu cầu nghề nghiệp nhưng mà nhập khẩu thì báo không đúng trên giấy tờ không có nhưng yêu cầu nhập
> (1 sao, 2025-08, 👍 80) App ổn , cho nhiêù khuyến mãi _(⚠ nội dung tích cực nhưng điểm 1 sao — khả năng lỗi nhập hoặc phản ứng sự kiện)_
> (1 sao, 2025-05, 👍 49) cảm ơn Vnpay rất nhiều vì đã cho mình xem được màn trình diễn đẹp... _(⚠ nội dung tích cực, khả năng nhầm điểm)_
> (1 sao, 2025-05, 👍 41) Gửi 1 sao cho phòng mkt của vnpay, quá tham lam. Thuê cả bot đi khẩu chiến với khách hàng.
> (1 sao, 2025-10, 👍 26) lỗi ko đặt đc vé tàu, cứ vào là bị thoát ra ngoài mong ad sửa lỗi
> (2 sao, 2025-05, 👍 22) liên kết ngân hàng tốn 10k, đã z thanh toán còn bị lỗi :)
> (1 sao, 2025-07, 👍 19) cho đổi điểm lấy voucher nhưng cứ đến giờ vào đổi là báo kết nối đến hệ thống gián đoạn
> (1 sao, 2025-05, 👍 18) t không đánh giá 1 sao vì drone show mà là vì chất lượng app tệ thật. Hồi trước dùng app thấy lỗi tùm lum la nên xoá, bây giờ tải lại định danh mãi vẫn không được, báo lỗi muốn khờ luôn.
> (1 sao, 2025-05, 👍 15) VNPay nên xem lại cái quét khuôn mặt nhé. mình có 1 khuôn mặt và bộ quét cứ bảo mình có nhiều khuôn mặt, quét k ra. Quét mãi nửa tiếng k ra. bực

**Diễn giải vấn đề chung từ các mẫu bình luận tiêu cực**
| Nhóm vấn đề | Số review | ThumbsUp | Từ khóa |
| --- | --- | --- | --- |
| Thanh toán / Ngân hàng / Liên kết | 61 | ~400+ | thanh toán, ngân hàng, liên kết |
| Xác thực / Định danh / Khuôn mặt | 58 | ~600+ | xác thực, định danh, khuôn mặt |
| Hỗ trợ / Tổng đài | 32 | ~80 | hỗ trợ, tổng đài |
| Nạp tiền / Trừ tiền / Đặt vé | 38 | ~60 | nạp tiền, trừ tiền, đặt vé |

**Thanh toán / Ngân hàng / Liên kết** — Tóm tắt: Lỗi liên kết thẻ/ngân hàng, bị trừ tiền nhưng giao dịch không hiển thị, hoàn tiền chậm. Đây là nhóm có tần suất cao nhất.

**Xác thực / Định danh / Khuôn mặt** — Tóm tắt: Không thể hoàn tất định danh (chụp CCCD, quét khuôn mặt), hệ thống báo lỗi liên tục. Nhóm có tổng thumbsUp cao nhất (~600+), thể hiện sự đồng thuận rộng của người dùng.

## 4) Trả lời câu hỏi chính

**1) Chất lượng ứng dụng: Người dùng đang gặp vấn đề gì?**
- Vấn đề xuất hiện nhiều nhất (1–4 sao): thanh toán, xác thực/định danh, đặt vé, OTP/đăng nhập.
- Vấn đề được tán thành nhiều nhất (thumbsUp): định danh (536), xác thực (513), không có (509), thanh toán (278).
- Tính năng được đề cập cụ thể: xác thực, khuôn mặt, ngân hàng, thanh toán, định danh, liên kết, tài khoản, tổng đài.

**Xếp hạng vấn đề theo tần suất xuất hiện (1–4 sao)**
| Vấn đề | Số review | ThumbsUp | Tháng đầu | Tháng cuối |
| --- | --- | --- | --- | --- |
| xác thực | 24 | 513 | 2025-05 | 2026-05 |
| khuôn mặt | 22 | 49 | 2025-05 | 2026-05 |
| ngân hàng | 21 | 65 | 2025-05 | 2026-05 |
| thanh toán | 21 | 278 | 2025-05 | 2026-05 |
| định danh | 21 | 536 | 2025-05 | 2026-05 |
| liên kết | 19 | 50 | 2025-05 | 2026-04 |
| hỗ trợ | 18 | 51 | 2025-05 | 2026-04 |
| tài khoản | 17 | 27 | 2025-05 | 2026-04 |
| thành công | 13 | 25 | 2025-05 | 2026-05 |

**2) Xu hướng thời gian: Chất lượng ứng dụng đang tốt lên hay xấu đi?**
- **Đánh giá trung bình giảm liên tục từ 2025-06 đến 2026-02**, chạm đáy 1.67 (02/2026).
- 2025-05 là tháng ngoại lệ (4065 reviews, avg 4.92) — khả năng cao do sự kiện lớn (kỷ niệm 50 năm Thống Nhất) tạo ra lượng review tích cực bất thường, không phản ánh chất lượng thực tế thường ngày.
- **Tháng có tỉ lệ review tiêu cực cao nhất: 2026-01** (91.7% ≤4 sao).