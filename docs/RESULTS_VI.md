# Kết quả pilot tương tác trong ChatGPT

## Kết luận được hỗ trợ
Đã thực thi sáu policy do trợ lý sinh trực tiếp trong phiên này và ba bundle
được ghép từ các policy đó. Cả chín cấu hình vượt bộ kiểm thử hiện có. Đây là
bằng chứng khả thi của việc tích hợp các artifact cụ thể vào tool, **không phải
đánh giá độc lập về hiệu quả LLM hoặc khả năng khái quát hóa**.

## Nguồn gốc
Trợ lý đã thiết kế và đọc tool, reference và test trước khi sinh candidate.
Sáu policy được viết trong một batch; ba bundle tái sử dụng các policy, không
phải ba lần lấy mẫu độc lập. Không dùng API. Không biết backend/model snapshot
chính xác từ môi trường này. Các file prompt là mô tả task đã trích xuất, không
phải toàn bộ context thực tế của phiên sinh. Các hạn chế này phải được giữ trong bài.

## Kết quả đã đo

| Cấu hình | Development | Final | Vi phạm của ứng viên |
|---|---:|---:|---:|
| Retry | 100/100 | 300/300 | 0 |
| Freshness | 100/100 | 300/300 | 0 |
| Cash reservation | 100/100 | 300/300 | 0 |
| Partial fills | 100/100 | 300/300 | 0 |
| Deduplication | 100/100 | 300/300 | 0 |
| Late fills | 100/100 | 300/300 | 0 |
| Market + Execution | 180/180 | 380/380 | 0 |
| Risk + Execution | 180/180 | 380/380 | 0 |
| Bốn policy phối hợp | 260/260 | 460/460 | 0 |
| Tổng | 1.220/1.220 | 3.020/3.020 | 0 |

Tổng ứng viên: 4.240 lượt. Kèm baseline trước tiến hóa: 8.480 lượt.
Mỗi họ kịch bản chạy với 20 seed; seed thay đổi đầu vào số và hoán vị ở một
kịch bản, không tạo các lần sinh LLM mới. Các baseline thiếu chức năng đều bị
từ chối ở final, phù hợp thiết kế của chúng; không thể từ đó suy ra tool vượt
trội so với công cụ khác. Các policy chưa trải qua một vòng sửa vì đều qua ngay.

Không có kết quả resampling-vs-feedback, tỷ lệ sửa hoặc chi phí API trong đợt này.
Thời gian thực thi cụ thể nằm trong results/reported/summary.json; đó là thời gian kiểm tra,
không bao gồm thời gian sinh mã trong hội thoại.

## Cách sử dụng khi viết
Có thể viết phần 'Preliminary feasibility evaluation' với bảng trên và mô tả
sáu artifact đơn + ba cấu hình dẫn xuất. Chưa đủ cho kết luận LLM đáng tin cậy,
hiệu quả feedback, generalization hoặc correctness hình thức.

Không mô tả bộ final là unseen/blind đối với người sinh trong đợt này. Không
viết 'nine independent generations', '4,240 LLM trials' hoặc '100% LLM repair'.

## Tái lập
Giải nén và chạy Python 3.10+:

```sh
python run.py
```

Script chỉ thực thi candidate đã đóng băng và baseline. Nó kiểm tra SHA-256,
không gọi LLM và không sinh lại candidate. Code, task descriptions, provenance,
CSV và báo cáo JSON đầy đủ nằm trong gói. Backend context sinh không thể tái lập
chính xác; chỉ phần thực thi các artifact có thể chạy lại.
