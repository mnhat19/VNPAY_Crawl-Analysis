"""
End-to-end review analysis pipeline for VNPAY Google Play reviews.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

EXPECTED_COLS = [
    "reviewId",
    "userName",
    "userImage",
    "content",
    "score",
    "thumbsUpCount",
    "reviewCreatedVersion",
    "at",
    "replyContent",
    "repliedAt",
    "appVersion",
]

ENCODING_CANDIDATES = ["utf-8-sig", "utf-8", "cp1258", "latin1"]

SHORT_PHRASES = {
    "ok",
    "oke",
    "okay",
    "t",
    "tot",
    "hay",
    "good",
    "nice",
    "bad",
    "app loi",
    "loi",
    "app",
    "ko",
    "khong",
    "k",
    "thanks",
    "cam on",
    "thank you",
    "haha",
    "huhu",
    "test",
    "test1",
    "aaa",
    "bbb",
    "ccc",
    "x",
    "xx",
    "xxx",
}

NEGATION_PREFIXES = {
    "không",
    "khong",
    "chưa",
    "chua",
    "cũng",
    "cung",
    "chẳng",
    "chang",
}

STOPWORDS = {
    "và",
    "va",
    "là",
    "la",
    "tôi",
    "toi",
    "bạn",
    "ban",
    "mình",
    "minh",
    "với",
    "voi",
    "này",
    "nay",
    "đây",
    "day",
    "rồi",
    "roi",
    "khi",
    "như",
    "nhu",
    "nữa",
    "nua",
    "chỉ",
    "chi",
    "một",
    "mot",
    "cái",
    "cai",
    "app",
    "ứng",
    "ung",
    "dụng",
    "dung",
    "vnpay",
    "rất",
    "rat",
    "quá",
    "qua",
    "tệ",
    "te",
    "tồi",
    "toi",
    "kém",
    "kem",
    "xấu",
    "xau",
    "tốt",
    "tot",
    "hay",
}

THEME_KEYWORDS = {
    "Xác thực/Định danh/Khuôn mặt": ["xác thực", "định danh", "khuôn mặt"],
    "Thanh toán/Ngân hàng/Liên kết": ["thanh toán", "ngân hàng", "liên kết"],
    "Hỗ trợ/Tổng đài": ["hỗ trợ", "tổng đài"],
    "Nạp tiền/Trừ tiền/Đặt vé": ["nạp tiền", "trừ tiền", "đặt vé"],
}

NEGATIVE_HINTS_FOLD = [
    "khong the",
    "khong duoc",
    "khong nhan",
    "khong thay",
    "khong vao",
    "khong mo",
    "khong thanh cong",
    "loi",
    "bi loi",
    "that bai",
    "tru tien",
    "bi tru",
    "mat tien",
    "khong ket noi",
    "he thong gian doan",
    "bi khoa",
    "khong the gui",
]


def read_csv_with_fallback(path: Path) -> tuple[pd.DataFrame, str]:
    last_error: Exception | None = None
    for enc in ENCODING_CANDIDATES:
        try:
            df = pd.read_csv(path, encoding=enc)
            return df, enc
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    raise RuntimeError(f"Cannot decode {path} with known encodings") from last_error


def normalize_whitespace(value: str | float | int | None) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    text = str(value)
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_text(value: str | float | int | None) -> str:
    text = normalize_whitespace(value)
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def strip_accents(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


STOPWORDS_FOLD = {strip_accents(w) for w in STOPWORDS}


def normalize_text_preserve_accents(value: str | float | int | None) -> str:
    text = clean_text(value).lower()
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_text_fold(value: str | float | int | None) -> str:
    return strip_accents(normalize_text_preserve_accents(value))


def classify_comment(value: str | float | int | None) -> str:
    if value is None:
        return "empty"
    raw = str(value).strip()
    if raw == "":
        return "empty"
    norm_fold = normalize_text_fold(raw)
    if norm_fold == "":
        return "empty"
    compact = norm_fold.replace(" ", "")
    if re.fullmatch(r"(.)\1{2,}", compact or ""):
        return "short"
    if len(norm_fold) <= 2:
        return "short"
    tokens = norm_fold.split()
    if len(tokens) == 1 and len(tokens[0]) <= 4:
        return "short"
    if norm_fold in SHORT_PHRASES:
        return "short"
    return "ok"


def missing_count(series: pd.Series) -> int:
    return int(series.isna().sum() + (series.astype(str).str.strip() == "").sum())


def iqr_outliers(series: pd.Series) -> int:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return 0
    q1 = values.quantile(0.25)
    q3 = values.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return int(((values < lower) | (values > upper)).sum())


def usability_level(col: str, missing_rate: float, unique_rate: float) -> str:
    if missing_rate <= 0.3 and (unique_rate >= 0.2 or col in {"score", "thumbsUpCount"}):
        return "High"
    if missing_rate <= 0.7 and unique_rate >= 0.05:
        return "Medium"
    return "Low"


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return ""
    line = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([line, sep] + body)


def tokenize(text: str) -> list[str]:
    tokens = [
        t
        for t in text.split()
        if t and len(t) >= 2 and strip_accents(t) not in STOPWORDS_FOLD
    ]
    return tokens


def extract_phrases(texts: Iterable[str], n: int, top_n: int) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for text in texts:
        tokens = tokenize(text)
        if len(tokens) < n:
            continue
        seen: set[str] = set()
        for i in range(len(tokens) - n + 1):
            gram = " ".join(tokens[i : i + n])
            seen.add(gram)
        for gram in seen:
            counter[gram] += 1
    return counter.most_common(top_n)


def is_feature_phrase(phrase: str) -> bool:
    parts = phrase.split()
    if not parts:
        return False
    return parts[0] not in NEGATION_PREFIXES


def detect_trend(month_counts: list[int]) -> str:
    if len(month_counts) < 4:
        return "không đủ dữ liệu"
    last = sum(month_counts[-3:])
    prev = sum(month_counts[-6:-3]) if len(month_counts) >= 6 else sum(month_counts[:-3])
    if prev == 0 and last > 0:
        return "tăng mạnh"
    if prev == 0 and last == 0:
        return "ổn định"
    ratio = (last - prev) / max(prev, 1)
    if ratio >= 0.5:
        return "tăng"
    if ratio <= -0.5:
        return "giảm"
    return "ổn định"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="")
    parser.add_argument("--output", type=str, default="vnpay_reviews_cleaned.csv")
    parser.add_argument("--report", type=str, default="analysis_report.md")
    parser.add_argument("--log", type=str, default="cleaning_log.jsonl")
    args = parser.parse_args()

    base_dir = Path(__file__).parent
    if args.input:
        input_path = Path(args.input)
    else:
        candidates = sorted(base_dir.glob("vnpay_reviews_gstore_*.csv"))
        if not candidates:
            print("No input CSV found.")
            return 1
        input_path = candidates[-1]

    output_path = base_dir / args.output
    report_path = base_dir / args.report
    log_path = base_dir / args.log

    df_raw, encoding_used = read_csv_with_fallback(input_path)

    for col in EXPECTED_COLS:
        if col not in df_raw.columns:
            df_raw[col] = ""

    df_raw = df_raw.copy()
    df_raw["content_raw"] = df_raw["content"].astype(str)
    df_raw["content"] = df_raw["content"].apply(clean_text)
    df_raw["content_norm"] = df_raw["content"].apply(normalize_text_preserve_accents)
    df_raw["content_fold"] = df_raw["content"].apply(normalize_text_fold)
    df_raw["content_len"] = df_raw["content"].str.len().fillna(0).astype(int)

    total_rows = len(df_raw)
    total_cols = len(df_raw.columns)

    score_num = pd.to_numeric(df_raw["score"], errors="coerce")
    invalid_score_mask = ~score_num.isin([1, 2, 3, 4, 5])
    invalid_score_count = int(invalid_score_mask.sum())

    thumbs_num = pd.to_numeric(df_raw["thumbsUpCount"], errors="coerce")
    df_raw["thumbsUpCount"] = thumbs_num.fillna(0).astype(int)

    at_dt_raw = pd.to_datetime(df_raw["at"], errors="coerce")
    replied_dt_raw = pd.to_datetime(df_raw["repliedAt"], errors="coerce")
    malformed_at = int(at_dt_raw.isna().sum())
    malformed_replied = int(replied_dt_raw.isna().sum())

    review_id_nonempty = df_raw["reviewId"].astype(str).str.strip() != ""
    dup_by_id = int(df_raw.loc[review_id_nonempty, "reviewId"].duplicated().sum())
    dup_by_content = int(
        df_raw.duplicated(subset=["content_fold", "userName", "at"], keep=False).sum()
    )

    encoding_issue_count = 0
    for col in df_raw.select_dtypes(include=["object", "string"]).columns:
        encoding_issue_count += int(df_raw[col].astype(str).str.contains("\ufffd|\uFFFD|�").sum())

    empty_or_short = df_raw["content"].apply(classify_comment)
    empty_count = int((empty_or_short == "empty").sum())
    short_count = int((empty_or_short == "short").sum())

    missing_stats = []
    for col in df_raw.columns:
        missing = missing_count(df_raw[col])
        missing_stats.append((col, missing, missing / max(total_rows, 1)))

    usability_rows = []
    for col, missing, rate in missing_stats:
        unique_rate = df_raw[col].nunique(dropna=True) / max(total_rows, 1)
        usability_rows.append(
            [
                col,
                f"{rate:.1%}",
                f"{unique_rate:.1%}",
                usability_level(col, rate, unique_rate),
            ]
        )

    outliers_thumbs = iqr_outliers(df_raw["thumbsUpCount"])
    outliers_length = iqr_outliers(df_raw["content_len"])

    # Cleaning pipeline
    clean_logs: list[dict] = []

    def log_step(step: str, before: int, after: int, note: str) -> None:
        clean_logs.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "step": step,
                "before": before,
                "after": after,
                "removed": before - after,
                "note": note,
            }
        )

    df = df_raw.copy()

    before = len(df)
    df = df[~invalid_score_mask].copy()
    log_step("remove_invalid_score", before, len(df), "Keep score in [1..5]")

    df["at_dt"] = pd.to_datetime(df["at"], errors="coerce")
    df = df.sort_values("at_dt", ascending=False, na_position="last")
    review_id = df["reviewId"].astype(str).str.strip()
    dedup_key = review_id.where(review_id != "", None)
    fallback_key = (
        df["content_fold"].fillna("")
        + "|"
        + df["userName"].astype(str).fillna("")
        + "|"
        + df["at"].astype(str).fillna("")
    )
    dedup_key = dedup_key.fillna(fallback_key)
    before = len(df)
    df = df.loc[~dedup_key.duplicated(keep="first")].copy()
    log_step("deduplicate", before, len(df), "reviewId else content+user+time")

    df["comment_flag"] = df["content"].apply(classify_comment)
    before = len(df)
    df = df[df["comment_flag"] == "ok"].copy()
    log_step("remove_short_or_empty", before, len(df), "Drop empty/low-info comments")

    df["score"] = pd.to_numeric(df["score"], errors="coerce").astype(int)
    df["thumbsUpCount"] = pd.to_numeric(df["thumbsUpCount"], errors="coerce").fillna(0).astype(int)
    df["at"] = pd.to_datetime(df["at"], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
    df["repliedAt"] = pd.to_datetime(df["repliedAt"], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
    df["reviewCreatedVersion"] = df["reviewCreatedVersion"].fillna("").astype(str).str.strip()
    df["appVersion"] = df["appVersion"].fillna("").astype(str).str.strip()
    df["content"] = df["content"].apply(clean_text)
    df["content_norm"] = df["content"].apply(normalize_text_preserve_accents)
    df["content_fold"] = df["content"].apply(normalize_text_fold)
    df["content_len"] = df["content"].str.len().fillna(0).astype(int)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    with open(log_path, "w", encoding="utf-8") as f:
        for entry in clean_logs:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Analysis stage
    analysis_df = df.copy()
    analysis_df["at_dt"] = pd.to_datetime(analysis_df["at"], errors="coerce")
    analysis_df["month"] = analysis_df["at_dt"].dt.to_period("M").astype(str)

    rating_dist = (
        analysis_df["score"].value_counts().sort_index().reindex([1, 2, 3, 4, 5], fill_value=0)
    )
    rating_rows = [[str(k), str(int(v))] for k, v in rating_dist.items()]

    monthly = (
        analysis_df.dropna(subset=["month"])
        .groupby("month", as_index=False)
        .agg(
            reviews=("score", "count"),
            avg_rating=("score", "mean"),
            negative_count=("score", lambda s: int((s <= 4).sum())),
            positive_count=("score", lambda s: int((s == 5).sum())),
        )
        .sort_values("month")
    )
    if not monthly.empty:
        monthly["negative_share"] = monthly["negative_count"] / monthly["reviews"]
        monthly["positive_share"] = monthly["positive_count"] / monthly["reviews"]
        monthly_rows = [
            [
                row["month"],
                str(int(row["reviews"])),
                f"{row['avg_rating']:.2f}",
                f"{row['negative_share']:.1%}",
            ]
            for _, row in monthly.iterrows()
        ]
    else:
        monthly_rows = []

    negative_df = analysis_df[analysis_df["score"] <= 4].copy()
    phrase_candidates = []
    phrase_candidates += extract_phrases(negative_df["content_norm"], 2, 20)
    phrase_candidates += extract_phrases(negative_df["content_norm"], 3, 20)
    seen_phrases = set()
    unique_phrases = []
    for phrase, count in phrase_candidates:
        if phrase in seen_phrases:
            continue
        seen_phrases.add(phrase)
        unique_phrases.append((phrase, count))
    top_phrases = unique_phrases[:12]

    issue_stats = []
    phrase_rows = []
    phrase_trends = []
    months_sorted = sorted(monthly["month"].tolist()) if not monthly.empty else []

    for phrase, count in top_phrases:
        mask = negative_df["content_norm"].str.contains(rf"\b{re.escape(phrase)}\b", regex=True)
        sub = negative_df[mask]
        phrase_count = int(sub.shape[0])
        thumbs_sum = int(sub["thumbsUpCount"].sum())
        negated_pattern = rf"\b(?:không|khong)\s+{re.escape(phrase)}\b"
        negated_count = int(negative_df["content_norm"].str.contains(negated_pattern, regex=True).sum())
        negated_ratio = negated_count / max(phrase_count, 1)
        first_month = sub["month"].min() if not sub.empty else ""
        last_month = sub["month"].max() if not sub.empty else ""
        phrase_rows.append([phrase, str(phrase_count), str(thumbs_sum), first_month, last_month])
        issue_stats.append(
            {
                "phrase": phrase,
                "count": phrase_count,
                "thumbs": thumbs_sum,
                "negated_ratio": negated_ratio,
                "first": first_month,
                "last": last_month,
            }
        )

        if months_sorted:
            counts_by_month = [
                int(sub[sub["month"] == m].shape[0])
                for m in months_sorted
            ]
            trend = detect_trend(counts_by_month)
        else:
            trend = "không đủ dữ liệu"
        phrase_trends.append((phrase, trend))

    # Top negative comments by thumbsUp (focus on issue-related keywords)
    issue_keywords = set([phrase for phrase, _ in top_phrases])
    for keywords in THEME_KEYWORDS.values():
        issue_keywords.update(keywords)
    neg_pattern = "|".join(
        [
            re.sub(r"\s+", r"\\s+", re.escape(p))
            for p in NEGATIVE_HINTS_FOLD
        ]
    )
    issue_masks = []
    for kw in issue_keywords:
        issue_masks.append(
            negative_df["content_norm"].str.contains(rf"\b{re.escape(kw)}\b", regex=True)
        )
    if issue_masks:
        issue_mask = issue_masks[0]
        for m in issue_masks[1:]:
            issue_mask = issue_mask | m
        neg_pool = negative_df[issue_mask].copy()
    else:
        neg_pool = negative_df
    if neg_pool.empty:
        neg_pool = negative_df
    if not neg_pool.empty:
        neg_hint_mask = neg_pool["content_fold"].str.contains(
            rf"\b(?:{neg_pattern})\b", regex=True
        )
        neg_pool = neg_pool[(neg_pool["score"] <= 3) | neg_hint_mask].copy()
        if neg_pool.empty:
            neg_pool = negative_df
    neg_top = (
        neg_pool.sort_values(["thumbsUpCount", "content_len"], ascending=[False, False])
        .drop_duplicates(subset=["content_norm"])
        .head(12)
    )

    # Theme summaries from negative reviews
    theme_rows = []
    theme_samples = []
    for theme, keywords in THEME_KEYWORDS.items():
        masks = []
        for kw in keywords:
            masks.append(
                negative_df["content_norm"].str.contains(rf"\b{re.escape(kw)}\b", regex=True)
            )
        if not masks:
            continue
        mask = masks[0]
        for m in masks[1:]:
            mask = mask | m
        sub = negative_df[mask].copy()
        if sub.empty:
            continue
        if neg_pattern:
            neg_hint_mask = sub["content_fold"].str.contains(
                rf"\b(?:{neg_pattern})\b", regex=True
            )
            sub = sub[(sub["score"] <= 3) | neg_hint_mask].copy()
            if sub.empty:
                continue
        theme_rows.append(
            [
                theme,
                str(int(sub.shape[0])),
                str(int(sub["thumbsUpCount"].sum())),
                ", ".join(keywords),
            ]
        )
        sample = (
            sub.sort_values(["thumbsUpCount", "content_len"], ascending=[False, False])
            .head(2)
            .to_dict("records")
        )
        theme_samples.append((theme, sample))

    # Version analysis
    version_col = "reviewCreatedVersion" if analysis_df["reviewCreatedVersion"].str.strip().any() else "appVersion"
    version_df = analysis_df[analysis_df[version_col].str.strip() != ""].copy()
    if not version_df.empty:
        version_stats = (
            version_df.groupby(version_col, as_index=False)
            .agg(
                reviews=("score", "count"),
                avg_rating=("score", "mean"),
                negative_share=("score", lambda s: float((s <= 4).mean())),
            )
            .sort_values(["reviews", "avg_rating"], ascending=[False, True])
        )
        version_stats = version_stats[version_stats["reviews"] >= 5]
        version_rows = [
            [
                row[version_col],
                str(int(row["reviews"])),
                f"{row['avg_rating']:.2f}",
                f"{row['negative_share']:.1%}",
            ]
            for _, row in version_stats.head(12).iterrows()
        ]
    else:
        version_rows = []

    # Spikes detection
    spike_notes = []
    if not monthly.empty and monthly["negative_count"].std() > 0:
        z_neg = (monthly["negative_count"] - monthly["negative_count"].mean()) / monthly["negative_count"].std()
        spikes_neg = monthly.loc[z_neg >= 1.5, "month"].tolist()
        if spikes_neg:
            spike_notes.append("Tháng có đột biến review tiêu cực: " + ", ".join(spikes_neg))
    if not monthly.empty and monthly["positive_count"].std() > 0:
        z_pos = (monthly["positive_count"] - monthly["positive_count"].mean()) / monthly["positive_count"].std()
        spikes_pos = monthly.loc[z_pos >= 1.5, "month"].tolist()
        if spikes_pos:
            spike_notes.append("Tháng có đột biến review tích cực: " + ", ".join(spikes_pos))

    # Trend of rating
    rating_trend_note = ""
    if len(monthly) >= 3:
        x = np.arange(len(monthly))
        y = monthly["avg_rating"].values
        slope = np.polyfit(x, y, 1)[0]
        if slope >= 0.05:
            rating_trend_note = "Xuất hiện xu hướng cải thiện đánh giá trung bình theo tháng."
        elif slope <= -0.05:
            rating_trend_note = "Đánh giá trung bình có xu hướng giảm theo tháng."
        else:
            rating_trend_note = "Đánh giá trung bình dao động nhẹ, chưa thấy xu hướng rõ."    

    issue_stats_filtered = [
        item
        for item in issue_stats
        if is_feature_phrase(item["phrase"]) and item["negated_ratio"] < 0.4
    ]
    issue_rank_count = sorted(issue_stats_filtered, key=lambda x: x["count"], reverse=True)
    issue_rank_thumbs = sorted(issue_stats_filtered, key=lambda x: x["thumbs"], reverse=True)
    issue_count_rows = [
        [item["phrase"], str(item["count"]), str(item["thumbs"]), item["first"], item["last"]]
        for item in issue_rank_count[:10]
    ]
    issue_thumb_rows = [
        [item["phrase"], str(item["thumbs"]), str(item["count"])]
        for item in issue_rank_thumbs[:10]
    ]

    feature_candidates = []
    feature_candidates += extract_phrases(negative_df["content_norm"], 2, 40)
    feature_candidates += extract_phrases(negative_df["content_norm"], 3, 20)
    feature_candidates += extract_phrases(negative_df["content_norm"], 4, 40)
    longer_phrases = [
        (phrase, count)
        for phrase, count in feature_candidates
        if len(phrase.split()) >= 3
    ]
    bigram_start_counts: dict[str, int] = {}
    for phrase, count in feature_candidates:
        parts = phrase.split()
        if len(parts) == 2:
            current = bigram_start_counts.get(parts[0], 0)
            if count > current:
                bigram_start_counts[parts[0]] = count
    top_issue_phrases = {item["phrase"] for item in issue_rank_count[:6]}
    seen_features = set()
    unique_features = []
    for phrase, count in feature_candidates:
        if phrase in seen_features:
            continue
        if not is_feature_phrase(phrase):
            continue
        parts = phrase.split()
        if len(parts) in (2, 3) and phrase not in top_issue_phrases:
            for longer, longer_count in longer_phrases:
                longer_parts = longer.split()
                if len(longer_parts) <= len(parts):
                    continue
                for i in range(len(longer_parts) - len(parts) + 1):
                    if parts == longer_parts[i : i + len(parts)]:
                        min_required = max(2, int(count * 0.7))
                        if len(longer_parts) == len(parts) + 1 and i == 1:
                            if longer_count >= 2:
                                phrase = longer
                                count = longer_count
                                break
                        if longer_count >= min_required:
                            phrase = longer
                            count = longer_count
                        break
                if phrase == longer:
                    break
        if parts and parts[0] == "thực":
            candidate = "xác " + phrase
            candidate_count = int(
                negative_df["content_norm"].str.contains(
                    rf"\b{re.escape(candidate)}\b", regex=True
                ).sum()
            )
            if candidate_count >= 2:
                phrase = candidate
                count = candidate_count
                parts = phrase.split()
        if not is_feature_phrase(phrase):
            continue
        if len(parts) >= 3 and phrase not in top_issue_phrases:
            last_token = parts[-1]
            if bigram_start_counts.get(last_token, 0) >= count:
                continue
        if parts and parts[-1] == "khuôn" and bigram_start_counts.get("khuôn", 0) > 0:
            continue
        if phrase in seen_features:
            continue
        negated_pattern = rf"\b(?:không|khong)\s+{re.escape(phrase)}\b"
        total_mask = negative_df["content_norm"].str.contains(
            rf"\b{re.escape(phrase)}\b", regex=True
        )
        total_count = int(total_mask.sum())
        if total_count > 0:
            negated_count = int(negative_df["content_norm"].str.contains(negated_pattern, regex=True).sum())
            if negated_count / total_count >= 0.4:
                continue
        seen_features.add(phrase)
        unique_features.append((phrase, count))
    feature_rows = [[p, str(c)] for p, c in unique_features[:12]]

    # Representative reviews
    representative_blocks = []
    for phrase, _ in top_phrases[:5]:
        mask = negative_df["content_norm"].str.contains(rf"\b{re.escape(phrase)}\b", regex=True)
        sub = negative_df[mask].copy()
        if sub.empty:
            continue
        sub = sub.sort_values(["thumbsUpCount", "content_len"], ascending=[False, False])
        sample_rows = sub.head(2)
        lines = [f"**Cụm từ khóa:** {phrase}"]
        for _, row in sample_rows.iterrows():
            text = row.get("content", "")
            if len(text) > 200:
                text = text[:197] + "..."
            lines.append(f"> ({row['score']} sao, {row['month']}) {text}")
        representative_blocks.append("\n".join(lines))

    # Data quality narrative
    quality_notes = []
    if invalid_score_count > 0:
        quality_notes.append(f"Có {invalid_score_count} review có rating không hợp lệ.")
    if empty_count + short_count > 0:
        ratio = (empty_count + short_count) / max(total_rows, 1)
        quality_notes.append(f"Tỷ lệ review trống/rất ngắn chiếm {ratio:.1%}.")
    if malformed_at > 0:
        quality_notes.append(f"Có {malformed_at} dòng bị lỗi định dạng thời gian ở cột at.")
    if encoding_issue_count > 0:
        quality_notes.append("Phát hiện ký tự lỗi mã hóa trong một số trường văn bản.")
    if outliers_thumbs > 0:
        quality_notes.append("Có dấu hiệu outlier ở số lượt like (thumbsUpCount).")

    # Build report
    report_lines = []
    report_lines.append("# Báo cáo phân tích reviews Google Play - VNPAY")
    report_lines.append("")
    report_lines.append(f"- Nguồn dữ liệu: {input_path.name}")
    report_lines.append(f"- Encoding: {encoding_used}")
    report_lines.append(f"- Số dòng: {total_rows}")
    report_lines.append(f"- Số cột: {total_cols}")
    report_lines.append("")

    report_lines.append("## 1) Data Profiling & Data Quality Assessment")
    report_lines.append("")
    report_lines.append("**Tổng quan chất lượng**")
    if quality_notes:
        report_lines.extend([f"- {note}" for note in quality_notes])
    else:
        report_lines.append("- Dữ liệu nhìn chung ổn định, ít lỗi rõ ràng.")
    report_lines.append("")

    report_lines.append("**Missing values (top 8)**")
    top_missing = sorted(missing_stats, key=lambda x: x[2], reverse=True)[:8]
    report_lines.append(
        md_table(
            ["Cột", "Số missing", "Tỷ lệ"],
            [[col, str(miss), f"{rate:.1%}"] for col, miss, rate in top_missing],
        )
    )
    report_lines.append("")

    report_lines.append("**Trùng lặp**")
    report_lines.append(f"- Duplicate theo reviewId: {dup_by_id}")
    report_lines.append(f"- Duplicate theo (content chuẩn hoá, userName, at): {dup_by_content}")
    report_lines.append("")

    report_lines.append("**Rating/Datetime**")
    report_lines.append(f"- Rating không hợp lệ: {invalid_score_count}")
    report_lines.append(f"- Datetime lỗi (at): {malformed_at}")
    report_lines.append(f"- Datetime lỗi (repliedAt): {malformed_replied}")
    report_lines.append("")

    report_lines.append("**Outliers & encoding**")
    report_lines.append(f"- Outlier thumbsUpCount: {outliers_thumbs}")
    report_lines.append(f"- Outlier độ dài review: {outliers_length}")
    report_lines.append(f"- Ký tự lỗi mã hóa: {encoding_issue_count}")
    report_lines.append("")

    report_lines.append("**Review ngắn vô nghĩa**")
    report_lines.append(f"- Rỗng/không nội dung: {empty_count}")
    report_lines.append(f"- Ngắn/low-info: {short_count}")
    report_lines.append("")

    report_lines.append("**Usability cột**")
    report_lines.append(
        md_table(
            ["Cột", "Missing", "Unique", "Usable"],
            usability_rows,
        )
    )
    report_lines.append("")

    report_lines.append("## 2) Data Cleaning & Preprocessing")
    report_lines.append("")
    report_lines.append("**Các bước làm sạch**")
    for entry in clean_logs:
        report_lines.append(
            f"- {entry['step']}: {entry['before']} -> {entry['after']} ({entry['removed']} removed)"
        )
    report_lines.append("")
    report_lines.append(f"- Output cleaned CSV: {output_path.name}")
    report_lines.append(f"- Log cleaning: {log_path.name}")
    report_lines.append("")

    report_lines.append("## 3) Business-Focused Review Analysis")
    report_lines.append("")

    report_lines.append("**Phân bố rating**")
    report_lines.append(md_table(["Rating", "Số lượng"], rating_rows))
    report_lines.append("")

    report_lines.append("**Xu hướng theo tháng**")
    if monthly_rows:
        report_lines.append(
            md_table(
                ["Tháng", "Reviews", "Avg rating", "Tỷ lệ <=4 sao"],
                monthly_rows,
            )
        )
    else:
        report_lines.append("- Không đủ dữ liệu thời gian để phân tích theo tháng.")
    if spike_notes:
        report_lines.extend([f"- {note}" for note in spike_notes])
    if rating_trend_note:
        report_lines.append(f"- {rating_trend_note}")
    report_lines.append("")

    report_lines.append("**Cụm từ phổ biến trong review 1-4 sao**")
    if phrase_rows:
        report_lines.append(
            md_table(
                ["Cụm từ", "Số review", "ThumbsUp", "Tháng đầu", "Tháng cuối"],
                phrase_rows,
            )
        )
    else:
        report_lines.append("- Chưa đủ dữ liệu để tìm cụm từ nổi bật.")
    report_lines.append("")

    report_lines.append("**Xu hướng cụm từ theo thời gian**")
    for phrase, trend in phrase_trends[:8]:
        report_lines.append(f"- {phrase}: {trend}")
    report_lines.append("")

    report_lines.append("**Liên hệ với version**")
    if version_rows:
        report_lines.append(
            md_table(
                ["Version", "Reviews", "Avg rating", "Tỷ lệ <=4 sao"],
                version_rows,
            )
        )
    else:
        report_lines.append("- Không đủ dữ liệu version để kết luận rõ.")
    report_lines.append("")

    report_lines.append("**Representative reviews**")
    if representative_blocks:
        report_lines.extend(representative_blocks)
    else:
        report_lines.append("- Chưa có representative reviews đủ mạnh.")
    report_lines.append("")

    report_lines.append("**Top bình luận tiêu cực được tán thành (1-4 sao)**")
    if not neg_top.empty:
        for _, row in neg_top.iterrows():
            text = row.get("content", "")
            if len(text) > 220:
                text = text[:217] + "..."
            report_lines.append(
                f"> ({row['score']} sao, {row['month']}, 👍 {row['thumbsUpCount']}) {text}"
            )
    else:
        report_lines.append("- Không đủ dữ liệu để trích bình luận tiêu cực nổi bật.")
    report_lines.append("")

    report_lines.append("**Diễn giải vấn đề chung từ các mẫu bình luận tiêu cực**")
    if theme_rows:
        report_lines.append(
            md_table(
                ["Nhóm vấn đề", "Số review", "ThumbsUp", "Từ khóa"],
                theme_rows,
            )
        )
        report_lines.append("")
        for theme, samples in theme_samples:
            report_lines.append(f"- **{theme}**")
            for sample in samples:
                text = sample.get("content", "")
                if len(text) > 180:
                    text = text[:177] + "..."
                report_lines.append(
                    f"> ({sample['score']} sao, {sample['month']}, 👍 {sample['thumbsUpCount']}) {text}"
                )
            report_lines.append("")
    else:
        report_lines.append("- Chưa đủ dữ liệu để diễn giải theo nhóm vấn đề.")
        report_lines.append("")

    report_lines.append("## 4) Trả lời câu hỏi chính")
    report_lines.append("")
    report_lines.append("**1) Chất lượng ứng dụng: Người dùng đang gặp vấn đề gì?**")
    if issue_rank_count:
        top_issue_text = ", ".join([item["phrase"] for item in issue_rank_count[:5]])
        report_lines.append(f"- Vấn đề xuất hiện nhiều nhất (1-4 sao): {top_issue_text}.")
    if issue_rank_thumbs:
        top_agree_text = ", ".join([item["phrase"] for item in issue_rank_thumbs[:3]])
        report_lines.append(f"- Vấn đề được tán thành nhiều nhất (thumbsUp): {top_agree_text}.")
    if feature_rows:
        feature_text = ", ".join([row[0] for row in feature_rows[:8]])
        report_lines.append(f"- Tính năng được đề cập cụ thể (trong review 1-4 sao): {feature_text}.")
    report_lines.append("")
    report_lines.append("**Xếp hạng vấn đề theo tần suất (1-4 sao)**")
    if issue_count_rows:
        report_lines.append(
            md_table(
                ["Vấn đề", "Số review", "ThumbsUp", "Tháng đầu", "Tháng cuối"],
                issue_count_rows,
            )
        )
    report_lines.append("")
    report_lines.append("**Vấn đề được tán thành nhiều nhất**")
    if issue_thumb_rows:
        report_lines.append(
            md_table(
                ["Vấn đề", "ThumbsUp", "Số review"],
                issue_thumb_rows,
            )
        )
    report_lines.append("")
    report_lines.append("**Tính năng được đề cập cụ thể (trong review 1-4 sao)**")
    if feature_rows:
        report_lines.append(md_table(["Cụm từ", "Số review"], feature_rows))
    report_lines.append("")
    report_lines.append("**2) Xu hướng thời gian: Chất lượng ứng dụng đang tốt lên hay xấu đi?**")
    if rating_trend_note:
        report_lines.append(f"- {rating_trend_note}")
    if spike_notes:
        report_lines.extend([f"- {note}" for note in spike_notes])
    report_lines.append("")

    report_lines.append("## 5) Nhận định dưới góc nhìn Product Manager")
    report_lines.append("")
    report_lines.append("- Ưu tiên xử lý nhóm vấn đề xuất hiện dày đặc và có thumbsUp cao trong review 1-4 sao.")
    report_lines.append("- Theo dõi rating theo tháng để khoanh vùng mốc suy giảm chất lượng.")
    report_lines.append("- Kết hợp dữ liệu version khi có đủ mẫu để liên hệ với từng bản cập nhật.")
    report_lines.append("- Chuẩn hóa thu thập version để tăng độ tin cậy khi phân tích theo release.")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print("Done. Outputs:")
    print(f"- Cleaned CSV: {output_path}")
    print(f"- Report: {report_path}")
    print(f"- Cleaning log: {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
