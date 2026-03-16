# SM3ChainGuard Performance Metrics

## Core Metrics

| Metric | Value |
|---|---:|
| Attack Detection Rate | 100.00% |
| Accuracy | 100.00% |
| Precision | 100.00% |
| Recall | 100.00% |
| F1 Score | 100.00% |
| Specificity | 100.00% |
| Balanced Accuracy | 100.00% |
| Clean False Positive Rate | 0.00% |

## Frame-Level Contextual Metrics

These frame-level metrics treat frames from tamper reports as positive-context samples, and frames from clean report as negative-context samples.

| Metric | Value |
|---|---:|
| Contextual Detection Rate | 83.33% |
| Accuracy | 84.38% |
| Precision | 100.00% |
| Recall | 83.33% |
| F1 Score | 90.91% |
| Specificity | 100.00% |
| Balanced Accuracy | 91.67% |

## Per-Attack Detection

| Attack | Detected | Failed Records | Failed Ratio | First Failed Step |
|---|:---:|---:|---:|---:|
| aggregate_hash_bitflip | Yes | 250 | 0.833333 | 50 |
| annotation_hash_bitflip | Yes | 250 | 0.833333 | 50 |
| annotation_text_edit | Yes | 250 | 0.833333 | 50 |
| camera_frame_index_edit | Yes | 250 | 0.833333 | 50 |
| delete_one_record | Yes | 249 | 0.832776 | 51 |
| duplicate_one_record | Yes | 251 | 0.833887 | 50 |
| final_hash_bitflip | Yes | 250 | 0.833333 | 50 |
| image_hash_bitflip | Yes | 250 | 0.833333 | 50 |
| previous_hash_bitflip | Yes | 250 | 0.833333 | 50 |
| reference_timestamp_edit | Yes | 250 | 0.833333 | 50 |
| rgb_block_occlusion | Yes | 250 | 0.833333 | 50 |
| rgb_gaussian_noise | Yes | 250 | 0.833333 | 50 |
| rgb_jpeg_reencode_low_quality | Yes | 250 | 0.833333 | 50 |
| swap_adjacent_records | Yes | 250 | 0.833333 | 51 |
| timestamp_hash_bitflip | Yes | 250 | 0.833333 | 50 |
