# Stress test report

- Videos rendered: **110**, passed QA: **110**, failed: **0**
- Total video length: 131.1 min; full run wall time 184.7 min with 3 workers on 4 CPU cores
- Re-run after fixes: cases [11, 28, 45, 62, 79, 106]. #106 was a real bug (very long topic made a 15 s Short run 29 s; fixed). The other 5 use a verbatim custom script, so their length is set by that script; the original duration check was wrong for them and was corrected.
- Loudness: min -14.2 / max -13.8 LUFS (target -14)
- Formats: {'long': 29, 'short': 81}
- Languages: {'ar': 16, 'en': 94}
- Niches: {'arabic_stories': 10, 'facts': 10, 'finance': 10, 'history': 10, 'kids_stories': 10, 'motivation': 10, 'mythology': 10, 'scary_stories': 10, 'science': 10, 'stoicism': 10, 'true_crime': 10}
- Caption styles: {'bold_pop': 22, 'clean': 22, 'hormozi': 22, 'minimal': 22, 'neon': 22}
- Art styles: {'3d_render': 13, 'anime': 14, 'cinematic': 14, 'comic': 14, 'dark_fantasy': 14, 'documentary': 13, 'oil_painting': 14, 'watercolor': 14}
- Voices: {'ar_female': 6, 'ar_male': 6, 'ar_male_eg': 4, 'en_female_news': 16, 'en_female_warm': 17, 'en_male_deep': 19, 'en_male_story': 23, 'en_male_uk': 19}

| # | niche | format | lang | captions | requested | actual | scenes | LUFS | MB | result |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | scary_stories | short | en | bold_pop | 45 | 48.9s | 9 | -14.0 | 20.66 | ✅ |
| 1 | history | short | en | bold_pop | default | 55.0s | 10 | -14.0 | 25.01 | ✅ |
| 2 | motivation | short | en | hormozi | 35 | 37.7s | 7 | -14.1 | 18.58 | ✅ |
| 3 | facts | long | en | hormozi | 180 | 180.3s | 20 | -14.1 | 74.97 | ✅ |
| 4 | true_crime | short | en | clean | 15 | 17.8s | 3 | -14.1 | 9.38 | ✅ |
| 5 | science | short | ar | clean | 15 | 19.8s | 3 | -14.0 | 6.32 | ✅ |
| 6 | finance | short | en | neon | 55 | 57.7s | 11 | -14.1 | 25.92 | ✅ |
| 7 | mythology | long | en | neon | 60 | 71.5s | 7 | -14.1 | 29.6 | ✅ |
| 8 | stoicism | short | en | minimal | 55 | 59.2s | 11 | -14.1 | 29.44 | ✅ |
| 9 | kids_stories | short | en | minimal | 15 | 19.8s | 3 | -14.0 | 7.69 | ✅ |
| 10 | arabic_stories | short | ar | bold_pop | 55 | 59.8s | 11 | -14.0 | 30.19 | ✅ |
| 11 | scary_stories | long | en | bold_pop | 150 | 29.9s | 6 | -14.1 | 10.91 | ✅ |
| 12 | history | short | en | hormozi | 55 | 59.2s | 11 | -14.1 | 26.98 | ✅ |
| 13 | motivation | short | en | hormozi | 15 | 13.8s | 2 | -13.8 | 5.48 | ✅ |
| 14 | facts | short | en | clean | 35 | 32.4s | 7 | -14.0 | 15.18 | ✅ |
| 15 | true_crime | long | en | clean | 180 | 202.7s | 20 | -14.0 | 84.62 | ✅ |
| 16 | science | short | en | neon | 60 | 59.3s | 12 | -14.0 | 25.96 | ✅ |
| 17 | finance | short | en | neon | default | 54.1s | 10 | -14.1 | 24.96 | ✅ |
| 18 | mythology | short | ar | minimal | 55 | 53.0s | 10 | -14.0 | 24.1 | ✅ |
| 19 | stoicism | long | en | minimal | 120 | 136.1s | 13 | -14.0 | 61.99 | ✅ |
| 20 | kids_stories | short | en | bold_pop | 60 | 59.3s | 12 | -14.1 | 33.04 | ✅ |
| 21 | arabic_stories | short | ar | bold_pop | 55 | 59.6s | 11 | -14.0 | 26.29 | ✅ |
| 22 | scary_stories | short | en | hormozi | 35 | 41.5s | 7 | -13.9 | 15.62 | ✅ |
| 23 | history | long | en | hormozi | 180 | 191.7s | 20 | -14.1 | 78.47 | ✅ |
| 24 | motivation | short | en | clean | 55 | 56.3s | 11 | -14.0 | 28.77 | ✅ |
| 25 | facts | short | en | clean | 25 | 27.1s | 4 | -14.0 | 11.48 | ✅ |
| 26 | true_crime | short | en | neon | 15 | 16.9s | 3 | -14.1 | 7.42 | ✅ |
| 27 | science | long | en | neon | 120 | 124.3s | 13 | -14.0 | 51.2 | ✅ |
| 28 | finance | short | en | minimal | 55 | 26.6s | 6 | -14.0 | 13.56 | ✅ |
| 29 | mythology | short | en | minimal | default | 54.1s | 10 | -14.1 | 23.31 | ✅ |
| 30 | stoicism | short | en | bold_pop | 45 | 50.9s | 9 | -14.0 | 23.25 | ✅ |
| 31 | kids_stories | long | ar | bold_pop | 60 | 80.9s | 7 | -14.0 | 36.23 | ✅ |
| 32 | arabic_stories | short | ar | hormozi | 60 | 58.7s | 11 | -14.0 | 28.76 | ✅ |
| 33 | scary_stories | short | en | hormozi | 35 | 39.4s | 7 | -14.0 | 14.51 | ✅ |
| 34 | history | short | en | clean | 45 | 45.5s | 9 | -14.0 | 20.61 | ✅ |
| 35 | motivation | long | en | clean | 180 | 181.3s | 20 | -14.0 | 72.73 | ✅ |
| 36 | facts | short | en | neon | 15 | 15.0s | 2 | -14.1 | 6.92 | ✅ |
| 37 | true_crime | short | en | neon | 25 | 27.5s | 5 | -14.1 | 11.82 | ✅ |
| 38 | science | short | en | minimal | 45 | 46.2s | 9 | -14.1 | 21.01 | ✅ |
| 39 | finance | long | en | minimal | 90 | 94.5s | 10 | -14.1 | 40.26 | ✅ |
| 40 | mythology | long | en | bold_pop | 420 | 460.4s | 47 | -14.1 | 194.07 | ✅ |
| 41 | stoicism | short | en | bold_pop | default | 53.9s | 10 | -14.0 | 21.91 | ✅ |
| 42 | kids_stories | short | en | hormozi | 60 | 59.8s | 12 | -14.0 | 31.46 | ✅ |
| 43 | arabic_stories | long | en | hormozi | 90 | 97.9s | 10 | -14.0 | 44.22 | ✅ |
| 44 | scary_stories | short | ar | clean | 25 | 30.9s | 5 | -14.0 | 13.55 | ✅ |
| 45 | history | short | en | clean | 60 | 27.7s | 6 | -14.1 | 12.54 | ✅ |
| 46 | motivation | short | en | neon | 45 | 47.7s | 9 | -14.1 | 22.43 | ✅ |
| 47 | facts | long | en | neon | 120 | 118.3s | 13 | -14.1 | 49.3 | ✅ |
| 48 | true_crime | short | en | minimal | 25 | 27.8s | 5 | -14.0 | 9.99 | ✅ |
| 49 | science | short | en | minimal | 55 | 56.8s | 11 | -14.1 | 24.9 | ✅ |
| 50 | finance | short | en | bold_pop | 25 | 28.1s | 5 | -14.1 | 12.6 | ✅ |
| 51 | mythology | long | en | bold_pop | 150 | 168.3s | 17 | -14.1 | 63.72 | ✅ |
| 52 | stoicism | short | en | hormozi | 45 | 50.9s | 9 | -14.1 | 25.53 | ✅ |
| 53 | kids_stories | short | en | hormozi | 45 | 49.0s | 9 | -14.0 | 23.56 | ✅ |
| 54 | arabic_stories | short | ar | clean | 15 | 19.8s | 3 | -14.0 | 9.36 | ✅ |
| 55 | scary_stories | long | en | clean | 90 | 106.7s | 10 | -14.1 | 40.44 | ✅ |
| 56 | history | short | en | neon | 15 | 19.7s | 3 | -14.0 | 8.96 | ✅ |
| 57 | motivation | short | ar | neon | 15 | 19.8s | 3 | -14.0 | 9.2 | ✅ |
| 58 | facts | short | en | minimal | 55 | 53.8s | 11 | -14.0 | 24.31 | ✅ |
| 59 | true_crime | long | en | minimal | 180 | 198.4s | 20 | -14.0 | 81.78 | ✅ |
| 60 | science | short | en | bold_pop | default | 50.4s | 10 | -14.0 | 25.86 | ✅ |
| 61 | finance | short | en | bold_pop | 60 | 54.8s | 11 | -14.2 | 23.78 | ✅ |
| 62 | mythology | short | en | hormozi | 55 | 28.2s | 6 | -14.0 | 14.14 | ✅ |
| 63 | stoicism | long | en | hormozi | 60 | 72.8s | 7 | -14.0 | 29.72 | ✅ |
| 64 | kids_stories | short | en | clean | 45 | 50.4s | 9 | -14.0 | 25.8 | ✅ |
| 65 | arabic_stories | short | ar | clean | 35 | 43.4s | 7 | -14.0 | 20.23 | ✅ |
| 66 | scary_stories | short | en | neon | 15 | 19.5s | 3 | -14.0 | 7.62 | ✅ |
| 67 | history | long | en | neon | 150 | 162.5s | 17 | -14.0 | 75.24 | ✅ |
| 68 | motivation | short | en | minimal | 25 | 28.7s | 5 | -14.1 | 12.49 | ✅ |
| 69 | facts | short | en | minimal | 25 | 25.2s | 5 | -14.1 | 11.88 | ✅ |
| 70 | true_crime | short | en | bold_pop | 35 | 42.5s | 7 | -14.0 | 17.04 | ✅ |
| 71 | science | long | en | bold_pop | 180 | 187.8s | 20 | -14.0 | 78.46 | ✅ |
| 72 | finance | short | en | hormozi | 35 | 35.3s | 7 | -14.0 | 15.12 | ✅ |
| 73 | mythology | short | en | hormozi | 60 | 59.3s | 12 | -14.1 | 26.32 | ✅ |
| 74 | stoicism | short | en | clean | default | 55.8s | 10 | -14.1 | 29.27 | ✅ |
| 75 | kids_stories | long | en | clean | 90 | 107.1s | 10 | -14.1 | 49.66 | ✅ |
| 76 | arabic_stories | short | ar | neon | 35 | 42.7s | 7 | -14.0 | 20.24 | ✅ |
| 77 | scary_stories | short | en | neon | default | 58.2s | 10 | -14.1 | 25.2 | ✅ |
| 78 | history | short | en | minimal | 35 | 34.7s | 6 | -14.0 | 15.17 | ✅ |
| 79 | motivation | long | en | minimal | 120 | 26.9s | 6 | -14.1 | 12.63 | ✅ |
| 80 | facts | long | en | bold_pop | 420 | 416.6s | 47 | -14.0 | 176.79 | ✅ |
| 81 | true_crime | short | en | bold_pop | 45 | 50.8s | 9 | -14.0 | 21.31 | ✅ |
| 82 | science | short | en | hormozi | 25 | 27.1s | 5 | -14.1 | 13.55 | ✅ |
| 83 | finance | long | ar | hormozi | 150 | 176.0s | 17 | -14.0 | 74.27 | ✅ |
| 84 | mythology | short | en | clean | default | 53.2s | 10 | -14.0 | 26.3 | ✅ |
| 85 | stoicism | short | en | clean | default | 57.2s | 10 | -14.0 | 25.39 | ✅ |
| 86 | kids_stories | short | en | neon | 25 | 28.6s | 5 | -14.1 | 16.58 | ✅ |
| 87 | arabic_stories | long | ar | neon | 60 | 73.7s | 7 | -14.0 | 33.17 | ✅ |
| 88 | scary_stories | short | en | minimal | 60 | 55.2s | 10 | -14.1 | 23.56 | ✅ |
| 89 | history | short | en | minimal | 25 | 28.4s | 5 | -14.0 | 11.79 | ✅ |
| 90 | motivation | short | en | bold_pop | 25 | 25.9s | 5 | -14.1 | 11.43 | ✅ |
| 91 | facts | long | en | bold_pop | 90 | 86.0s | 10 | -14.1 | 34.8 | ✅ |
| 92 | true_crime | short | en | hormozi | 60 | 59.2s | 12 | -14.0 | 27.13 | ✅ |
| 93 | science | short | en | hormozi | 55 | 57.4s | 11 | -14.0 | 25.54 | ✅ |
| 94 | finance | short | en | clean | 15 | 15.8s | 2 | -14.0 | 5.76 | ✅ |
| 95 | mythology | long | en | clean | 180 | 206.7s | 20 | -14.0 | 85.67 | ✅ |
| 96 | stoicism | short | ar | neon | 45 | 55.5s | 9 | -14.0 | 23.7 | ✅ |
| 97 | kids_stories | short | en | neon | 35 | 41.3s | 7 | -14.1 | 19.11 | ✅ |
| 98 | arabic_stories | short | ar | minimal | 55 | 59.3s | 11 | -14.0 | 25.91 | ✅ |
| 99 | scary_stories | long | en | minimal | 120 | 135.6s | 13 | -14.1 | 50.51 | ✅ |
| 100 | history | short | en | bold_pop | default | 53.3s | 10 | -14.0 | 25.94 | ✅ |
| 101 | motivation | short | en | bold_pop | 60 | 59.2s | 12 | -14.1 | 26.12 | ✅ |
| 102 | facts | short | en | hormozi | 60 | 59.2s | 12 | -14.0 | 27.38 | ✅ |
| 103 | true_crime | long | en | hormozi | 180 | 194.5s | 20 | -14.1 | 80.6 | ✅ |
| 104 | science | short | en | clean | 55 | 57.0s | 11 | -14.1 | 27.18 | ✅ |
| 105 | finance | short | en | clean | default | 54.9s | 10 | -14.0 | 24.05 | ✅ |
| 106 | mythology | short | en | neon | 15 | 17.0s | 2 | -14.0 | 6.62 | ✅ |
| 107 | stoicism | long | en | neon | 90 | 100.8s | 10 | -14.1 | 43.97 | ✅ |
| 108 | kids_stories | short | en | minimal | 55 | 58.4s | 11 | -14.0 | 31.77 | ✅ |
| 109 | arabic_stories | short | ar | minimal | 60 | 53.1s | 10 | -14.0 | 24.76 | ✅ |
