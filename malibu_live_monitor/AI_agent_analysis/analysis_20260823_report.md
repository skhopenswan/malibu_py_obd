# 迈锐宝 LFV 200km 高速动力与变速箱油温诊断汇总

- 样本: 28677 行 . 周期 203 分钟 . 采样率 2.35Hz
- 车速峰值 132 km/h, 高速(>80)占比 37%
- RPM峰值 4832 rpm, Boost峰值 +0.49 bar
- 事件Boost P98上限 +0.38 bar (若极低->涡轮/进气受限; 需结合油门)
- LTFT 均值 -0.7% 范围 -5.5..8.6% (持续大正>+10 才提示漏气)
- TFT 范围 69..85 C (正常70-95)

## 急加速事件判定 (共 16)
| 类型 | 次数 |
|---|---|
| 真实增压 | 2 |
| 疑似降档 | 5 |
| 扭矩受限 | 7 |
| 疑似滑差 | 3 |
| 增压不足 | 14 |

### 明细
```
  E01 t=   4.2min dur= 6.3s spd=  9-> 10 boost98=-0.40 MAFmax= 18.7 RPMmax=1584 loadmax= 46 TFT  73-> 73 [增压不足 + 疑似降档 + 扭矩受限]
  E02 t=   5.1min dur=12.5s spd= 29-> 61 boost98=+0.47 MAFmax= 98.2 RPMmax=3202 loadmax=100 TFT  73-> 74 [真实增压 + 疑似滑差]
  E03 t=  19.4min dur= 7.2s spd= 91-> 88 boost98=-0.13 MAFmax= 43.7 RPMmax=2069 loadmax= 81 TFT  74-> 74 [增压不足 + 疑似降档 + 扭矩受限]
  E04 t=  34.6min dur= 8.3s spd= 40-> 48 boost98=-0.26 MAFmax= 21.2 RPMmax=1802 loadmax= 75 TFT  74-> 74 [增压不足 + 疑似降档]
  E05 t=  37.3min dur= 6.3s spd= 49-> 45 boost98=-0.41 MAFmax= 12.8 RPMmax=1402 loadmax= 57 TFT  75-> 75 [增压不足]
  E06 t=  38.1min dur= 3.1s spd= 65-> 61 boost98=-0.35 MAFmax= 13.9 RPMmax=1603 loadmax= 65 TFT  76-> 76 [增压不足]
  E07 t=  48.9min dur= 3.6s spd=101->102 boost98=-0.67 MAFmax=  7.3 RPMmax=2032 loadmax= 13 TFT  80-> 80 [增压不足]
  E08 t=  49.8min dur= 8.9s spd= 91-> 97 boost98=-0.34 MAFmax= 31.2 RPMmax=1928 loadmax= 62 TFT  80-> 80 [增压不足 + 扭矩受限]
  E09 t=  53.6min dur= 2.7s spd= 90-> 94 boost98=-0.13 MAFmax= 38.6 RPMmax=1838 loadmax= 78 TFT  79-> 79 [增压不足 + 扭矩受限]
  E10 t=  54.3min dur= 7.2s spd=127->119 boost98=-0.41 MAFmax= 36.0 RPMmax=2518 loadmax= 56 TFT  80-> 80 [增压不足 + 扭矩受限]
  E11 t=  56.6min dur= 6.3s spd= 95-> 84 boost98=-0.71 MAFmax=  7.8 RPMmax=1851 loadmax= 18 TFT  80-> 80 [增压不足]
  E12 t=  58.2min dur= 3.5s spd=110->119 boost98=+0.17 MAFmax= 72.1 RPMmax=3118 loadmax= 91 TFT  81-> 81 [真实增压 + 扭矩受限]
  E13 t=  93.5min dur= 3.5s spd= 36-> 48 boost98=-0.37 MAFmax= 23.8 RPMmax=2427 loadmax= 42 TFT  77-> 77 [增压不足]
  E14 t= 116.8min dur= 5.1s spd= 41-> 29 boost98=-0.47 MAFmax= 19.0 RPMmax=1682 loadmax= 40 TFT  79-> 79 [增压不足 + 疑似降档 + 疑似滑差]
  E15 t= 158.8min dur= 8.7s spd= 69-> 45 boost98=-0.33 MAFmax= 36.4 RPMmax=2148 loadmax= 64 TFT  77-> 77 [增压不足 + 疑似降档 + 扭矩受限 + 疑似滑差]
  E16 t= 169.2min dur= 2.2s spd=  8-> 17 boost98=-0.40 MAFmax= 25.8 RPMmax=2440 loadmax= 48 TFT  79-> 80 [增压不足]
```