# MVP-0 Complete Engineering Master Package

# طرح اجرایی جامع: سامانه مدیریت پرتفوی و معامله‌گری الگوریتمی رمزارز (نسخه ۴.۳)

> **تاریخ بازبینی:** ۱ اکتبر ۲۰۲۶ (بازبینی سوم تیم فنی)\
> **تاریخ اعمال وصله ۴.۳:** ۲ اکتبر ۲۰۲۶ (G0 Blocker Closure)\
> **نسخه سند:** ۴.۳ (وصله نهایی G0 --- بسته‌شدن ۴ شکاف بلاک‌کننده: Worker Lifecycle،
> Kill Switch Endpoint، Authentication/Authorization، PROTECTION_FAILED Retry Schedule؛
> به‌همراه اصلاح تناقض Scope مربوط به TimescaleDB/Vault در چک‌لیست)\
> **وضعیت:** G0 Blockers Closed — آماده برای ارزیابی نهایی/ورود کنترل‌شده به پیاده‌سازی\
> **اصل بنیادین:** تأیید صریح کاربر برای هر اقدام، fail-safe در برابر
> خطا، حفظ سرمایه اولویت بر بازدهی\
> **تغییر کلیدی نسخه ۴.۲:** اصلاح فرمول Position Sizing (خطای ریاضی)،
> اضافه شدن Synthetic Stop-Loss برای صرافی‌های داخلی، Dynamic Approval
> Timeout بر اساس تایم‌فریم، TimescaleDB به Post-MVP موکول شد، Slippage
> برای والکس/نوبیتکس تصحیح شد

------------------------------------------------------------------------

## تغییرات نسخه ۴.۳ (Changelog)

| # | تغییر | بخش | دلیل |
|---|---|---|---|
| ۱ | تعریف Background Worker Lifecycle با `asyncio` + FastAPI lifespan و محدودیت `workers=1` | G0 Patch | رفع شکاف بحرانی Worker |
| ۲ | اضافه شدن `POST /api/v1/system/emergency-stop` با Authorization و Admin-only authorization | API Contract / Kill Switch | رفع شکاف بحرانی Kill Switch Endpoint |
| ۳ | تثبیت Authentication برای `/api/v1/*` با Bearer API Key و تعریف تفکیک `MVP0_API_KEY` و `MVP0_ADMIN_API_KEY` | API Security Contract | رفع شکاف بحرانی Authentication |
| ۴ | تثبیت برنامه retry برای `PROTECTION_FAILED`: `t=0s, 5s, 15s` و مسیر جبرانی نهایی | Order State Machine | رفع شکاف بحرانی Retry Interval |
| ۵ | اصلاح چک‌لیست MVP-0: حذف نصب TimescaleDB و Vault از prereqهای MVP-0 | §25 | رفع تناقض با Explicitly Excluded From MVP-0 |
| ۶ | هم‌ترازسازی دیاگرام لایه‌های مشترک با Scope واقعی MVP-0 | §2.2 | حذف اجزای Post-MVP از معماری فعال |
| ۷ | هم‌ترازسازی IPS با Dynamic Approval Timeout؛ `None` به‌عنوان Dynamic و مقدار ۳–۲۴۰ دقیقه به‌عنوان سقف کاهنده | §10.1/§13.6 | رفع تعارض قرارداد Timeout |

---

## تغییرات نسخه ۴.۲ (Changelog)

  -----------------------------------------------------------------------
  \#                تغییر             بخش               دلیل
  ----------------- ----------------- ----------------- -----------------
  ۱                 اصلاح فرمول       ۵.۱               پاسخ به اشکال P0
                    Position Sizing                     #۱ --- ضرب E_p
                    (خطای ریاضی)                        غلط بود

  ۲                 اضافه شدن         ۵.۲               پاسخ به اشکال P0
                    Synthetic                           #۲ ---
                    Stop-Loss برای                      والکس/نوبیتکس
                    صرافی‌های داخلی                      بدون OCO

  ۳                 Dynamic Approval  ۱۳.۶              پاسخ به اشکال P1
                    Timeout بر اساس                     #۳ --- تایم‌اوت
                    تایم‌فریم                            ثابت نامناسب

  ۴                 TimescaleDB از    ۲.۱، ۱۲           پاسخ به اشکال P1
                    MVP-0 به Post-MVP                   #۴ --- بیش‌مهندسی
                    منتقل شد                            

  ۵                 Slippage برای     ۵.۱               پاسخ به اشکال P2
                    والکس/نوبیتکس                       
                    تصحیح شد                            
                    (۰.۳%-۰.۵٪)                         

  ۶                 Concept Drift     ۱۷                پاسخ به اشکال P2
                    معیار کمی مشخص شد                   
                    (PSI \> 0.2)                        

  ۷                 Vault از MVP-0 به ۳.۳، ۱۲           پاسخ به اشکال P2
                    Post-MVP منتقل شد                   
                    (encrypted .env                     
                    کافی)                               
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## تغییرات نسخه ۴.۱ (Changelog)

  -----------------------------------------------------------------------
  \#                تغییر             بخش               دلیل
  ----------------- ----------------- ----------------- -----------------
  ۱                 معرفی MVP-0:      بخش جدید ۱.۳      پاسخ به نقدهای ۱،
                    تعریف حداقلی                        ۲، ۳، ۵، ۹ ---
                    محصول                               scope زیاد

  ۲                 Go از MVP حذف شد، ۲.۱               پاسخ به نقد ۱ ---
                    فقط Python                          premature
                                                        optimization

  ۳                 JEV از MVP حذف،   ۲۳                پاسخ به نقد ۲ ---
                    جایگزین با                          ابهام استراتژیک
                    Baseline Metrics                    

  ۴                 Roadmap با        ۱۲                پاسخ به نقد ۳ ---
                    team-size                           غیرواقع‌بینانه
                    assumptions                         

  ۵                 Paper Trading با  ۱۲.۳              پاسخ به نقد ۶ ---
                    Docker Network                      ایزوله نیست
                    Isolation                           

  ۶                 Kill Switch با    ۱۱.۴              پاسخ به نقد ۷ ---
                    ماتریس اختیار و                     مکانیزم مبهم
                    Fire Drill                          

  ۷                 PWA با استراتژی   ۱۹.۲              پاسخ به نقد ۸ ---
                    آفلاین صریح                         بدون آفلاین
                                                        استراتژی

  ۸                 RLS از MVP حذف،   ۱۶.۲              پاسخ به نقد ۹ ---
                    با Benchmark Gate                   بار عملکردی

  ۹                 API Key Leak      ۱۳.۵              پاسخ به نقد ۱۰
                    Runbook                             --- سناریوی leak

  ۱۰                Wallex/Nobitex    ۱۵.۴              پاسخ به نقد ۴ ---
                    API امنیت مستند                     ناقص

  ۱۱                Baseline Model    ۱۷.۳              پاسخ به نقد ۵ ---
                    تعریف شد                            بدون baseline

  ۱۲                User Approval     ۱۳.۶              پاسخ به پیشنهاد ز
                    Timeout SLA                         

  ۱۳                Chaos Engineering ۹.۴               پاسخ به پیشنهاد د
                    Checklist                           

  ۱۴                One-Page Runbooks ۱۳.۷              پاسخ به پیشنهاد ه
                    برای ۱۰ نقطه شکست                   

  ۱۵                Decision Log با   ۲۱.۵              پاسخ به پیشنهاد ب
                    Visual Audit UI                     
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## فهرست مطالب

0.  [جدول تغییرات نسخه ۴.۳](#تغییرات-نسخه-۴۳-changelog)
0.1 [جدول تغییرات نسخه ۴.۱](#تغییرات-نسخه-۴۱-changelog)
1.  [جدول پاسخ به بازبینی تیم فنی (Traceability
    Matrix)](#۰-جدول-پاسخ-به-بازبینی-تیم-فنی-traceability-matrix)
2.  [اصول غیرقابل‌مذاکره و هدف سیستم](#۱-اصول-غیرقابل‌مذاکره-و-هدف-سیستم)
3.  [معماری سیستم و انتخاب Stack
    فناوری](#۲-معماری-سیستم-و-انتخاب-stack-فناوری)
4.  [لایه‌های مشترک (Shared Layers)](#۳-لایه‌های-مشترک-shared-layers)
5.  [سیستم سیگنال‌دهی و قواعد تولید
    سیگنال](#۴-سیستم-سیگنال‌دهی-و-قواعد-تولید-سیگنال)
6.  [الگوریتم‌های مدیریت ریسک و Position
    Sizing](#۵-الگوریتم‌های-مدیریت-ریسک-و-position-sizing)
7.  [سیستم مدیریت سبد (Portfolio
    Management)](#۶-سیستم-مدیریت-سبد-portfolio-management)
8.  [چرخه تأیید، اجرا و حفاظت](#۷-چرخه-تأیید-اجرا-و-حفاظت)
9.  [Conflict Resolution و اولویت‌بندی
    سیگنال‌ها](#۸-conflict-resolution-و-اولویت‌بندی-سیگنال‌ها)
10. [کیفیت، آزمون و دروازه‌های
    مرحله‌ای](#۹-کیفیت-آزمون-و-دروازه‌های-مرحله‌ای)
11. [ورودی کاربر و سیاست سرمایه‌گذاری
    (IPS)](#۱۰-ورودی-کاربر-و-سیاست-سرمایه‌گذاری-ips)
12. [مدیریت ریسک ۸ سطحی](#۱۱-مدیریت-ریسک-۸-سطحی)
13. [نقشه راه پیاده‌سازی (بازنگری‌شده)](#۱۲-نقشه-راه-پیاده‌سازی-بازنگری‌شده)
14. [SLA، RTO و RPO و Operational
    Runbook](#۱۳-sla-rto-و-rpo-و-operational-runbook)
15. [Data Governance و Privacy](#۱۴-data-governance-و-privacy)
16. [Compliance و Regulatory Risk](#۱۵-compliance-و-regulatory-risk)
17. [استراتژی Multi-tenancy](#۱۶-استراتژی-multi-tenancy)
18. [مدل‌های ML: Shadow Mode، Promotion و A/B
    Testing](#۱۷-مدل‌های-ml-shadow-mode-promotion-و-ab-testing)
19. [Stress Testing Module](#۱۸-stress-testing-module)
20. [Mobile-first UI و UX](#۱۹-mobile-first-ui-و-ux)
21. [Exit Strategy برای وابستگی‌های
    خارجی](#۲۰-exit-strategy-برای-وابستگی‌های-خارجی)
22. [ایده‌های تکمیلی برای ارتقای طرح](#۲۱-ایده‌های-تکمیلی-برای-ارتقای-طرح)
23. [تحلیل نقاط شکست معماری و ماتریس
    ریسک](#۲۲-تحلیل-نقاط-شکست-معماری-و-ماتریس-ریسک)
24. [ارزیابی JEV و Baseline Metrics](#۲۳-ارزیابی-jev-و-baseline-metrics)
25. [KPI‌های بلندمدت (۶-۱۲ ماه)](#۲۴-kpiهای-بلندمدت-۶-۱۲-ماه)
26. [چک‌لیست نهایی پیش از کدنویسی](#۲۵-چک‌لیست-نهایی-پیش-از-کدنویسی)
27. [اولویت‌های نهایی محصول](#۲۶-اولویت‌های-نهایی-محصول)
28. [قراردادهای نهایی G0 v4.3](#v43-final-g0-blocker-closure--implementation-contracts)

------------------------------------------------------------------------

## ۱. اصول غیرقابل‌مذاکره و هدف سیستم

### ۰.۱ جدول پاسخ به بازبینی دوم تیم فنی (Traceability Matrix)

#### نقاط ضعف (۹ مورد + ۱ مورد تکمیلی)

  -------------------------------------------------------------------------
  \#          نقطه ضعف         وضعیت       تغییر اعمال‌شده   بخش
  ----------- ---------------- ----------- ---------------- ---------------
  ۱           تناقض معماری     ✅ حل‌شده    Go از MVP حذف    ۲.۱
              Go+Python                    شد، فقط Python.  
                                           Go فقط post-MVP  
                                           با ADR           

  ۲           ابهام استراتژیک  ✅ حل‌شده    JEV از MVP حذف،  ۲۳
              JEV                          جایگزین با       
                                           Baseline Metrics 
                                           ساده             

  ۳           نقشه‌راه          ✅ حل‌شده    Roadmap با       ۱۲
              غیرواقع‌بینانه                team-size        
                                           assumptions،     
                                           تفکیک MVP از     
                                           production       

  ۴           ریسک قانونی      ✅ حل‌شده    Wallex/Nobitex   ۱۵.۴
              ایران ناقص                   API امنیت مستند  
                                           شد               

  ۵           ML بدون Baseline ✅ حل‌شده    Baseline Model   ۱۷.۳
                                           تعریف شد:        
                                           rule-based       
                                           deterministic    

  ۶           Paper Trading    ✅ حل‌شده    Docker Network   ۱۲.۳
              ایزوله نیست                  Isolation با     
                                           egress deny      

  ۷           Kill Switch مبهم ✅ حل‌شده    ماتریس اختیار،   ۱۱.۴
                                           Fire Drill،      
                                           Override rules   

  ۸           PWA بدون         ✅ حل‌شده    استراتژی offline ۱۹.۲
              آفلاین‌استراتژی               صریح: read-only  
                                           cache، approval  
                                           ممنوع            

  ۹           RLS بار عملکردی  ✅ حل‌شده    RLS از MVP حذف،  ۱۶.۲
                                           Benchmark Gate   
                                           تعریف شد         

  ۱۰          API Key Leak     ✅ حل‌شده    Runbook کامل:    ۱۳.۵
              بدون workflow                Detection →      
                                           Immediate →      
                                           Recovery         
  -------------------------------------------------------------------------

#### پیشنهادات بهبود (۷ مورد)

  -------------------------------------------------------------------------
  \#           پیشنهاد       وضعیت        تغییر اعمال‌شده       بخش
  ------------ ------------- ------------ -------------------- ------------
  الف          تعریف MVP     ✅ انجام شد  MVP-0: single        ۱.۳
               واقعی                      exchange، single     
                                          user، Python-only    

  ب            Decision Log  ✅ انجام شد  رابط کاربری برای     ۲۱.۵
               با Visual                  نمایش «چرا این       
               Audit                      سیگنال»              

  ج            جایگزین JEV   ✅ انجام شد  Baseline Metrics:    ۲۳.۵
               با متریک ساده              rolling win rate،    
                                          expectancy           

  د            Chaos         ✅ انجام شد  Checklist با abort   ۹.۴
               Engineering                conditions و blast   
               سبک                        radius               

  ه            Runbook       ✅ انجام شد  قالب واحد برای ۱۰    ۱۳.۷
               یک‌صفحه‌ای برای              نقطه شکست            
               شکست‌ها                                          

  و            تفکیک Paper   ✅ انجام شد  Network مجزا، egress ۱۲.۳
               Trading با                 deny،                
               Docker                     LIVE_TRADING=false   
                                          immutable            

  ز            SLA برای      ✅ انجام شد  User Approval        ۱۳.۶
               تأییدیه کاربر              Timeout: ۵ دقیقه،    
                                          default = EXPIRED    
  -------------------------------------------------------------------------

------------------------------------------------------------------------

### ۱.۱ هدف و دامنه کاربردی

این سند مشخصات فنی و عملیاتی سامانه مدیریت پرتفوی و معامله‌گری الگوریتمی
رمزارز را تعریف می‌کند. سامانه دو حالت اجرای مجزا را پشتیبانی می‌کند:

  -----------------------------------------------------------------------
  حالت اجرا               کاربرد                  محدودیت‌های کلیدی
  ----------------------- ----------------------- -----------------------
  **حالت اتصال مستقیم     اتصال API به صرافی برای نیازمند API Key کاربر،
  (Direct Mode)**         اجرای خودکار سفارش      رعایت Rate Limit،
                                                  فعال‌سازی ۲FA

  **حالت سیگنال‌دهی        تولید و ارسال سیگنال به بدون اجرای خودکار،
  (Signal Mode)**         کانال یا پلتفرم         کاربر مسئول تأیید و
                                                  اجرای دستی
  -----------------------------------------------------------------------

سامانه در هر دو حالت فقط برای معاملات **Spot** طراحی شده است. Short،
مارجین، اهرم و مشتقات قابل‌اجرا نیستند.

### ۱.۲ اصول غیرقابل‌مذاکره

1.  **تأیید صریح پارامتر-محور:** هر سفارش نیازمند تأیید صریح و جداگانه
    کاربر با پارامترهای دقیق است.
2.  **مجموعه نمادهای مجاز:** مجموعه آغازین BTC/USDT، ETH/USDT و BNB/USDT
    است.
3.  **سقف‌های ریسک سخت‌گیرانه:** ریسک هر معامله حداکثر ۰.۵٪ از equity.
4.  **محدودیت سرمایه:** حداکثر ۵۰۰ USDT یا سقف پایین‌تر تعیین‌شده کاربر.
5.  **اصل تفکیک لایه‌ها:** Evidence، AI Reasoning، Risk Layer، Execution
    و Monitoring مجزا.
6.  **مدیریت انقضای خودکار:** سیگنال‌های تأییدنشده پس از انقضا EXPIRED.
7.  **حفظ سرمایه اولویت بر بازدهی.**

### ۱.۳ تعریف MVP-0: حداقل محصول قابل‌تولید (پاسخ به پیشنهاد الف)

> **نقد تیم فنی:** «بزرگ‌ترین ریسک اجرایی، scope زیاد برای یک تیم کوچک و
> نبود تعریف دقیق MVP اولیه است.»

**تصمیم:** تعریف «MVP-0» به‌عنوان کوچک‌ترین نسخه قابل‌تولید، پیش از ورود
قابلیت‌های پیشرفته.

#### جدول مقایسه MVP-0 vs Production Grade

  -----------------------------------------------------------------------
  قابلیت                  MVP-0 (حداقل)           Post-MVP (توسعه‌یافته)
  ----------------------- ----------------------- -----------------------
  **زبان برنامه‌نویسی**    Python فقط              Python + Go (با ADR)

  **تعداد کاربر**         Single-tenant (یک       Multi-tenant با RLS
                          کاربر)                  

  **صرافی**               یک صرافی (Wallex یا     چند صرافی با Adapter
                          Binance)                Pattern

  **ML / JEV**            بدون ML --- قواعد قطعی  Shadow Mode، A/B
                          (deterministic)         Testing، JEV

  **Multi-tenancy / RLS** بدون RLS --- single     PostgreSQL RLS با
                          user                    Benchmark Gate

  **Stress Testing**      ساده --- حداقل سناریو   کامل --- Monte Carlo، ۷
                                                  سناریو

  **Shadow Mode**         بدون                    ۵ مرحله lifecycle

  **A/B Testing**         بدون                    Framework با guardrails

  **Mobile PWA**          Responsive ساده         PWA کامل با offline
                                                  strategy

  **Monitoring**          Prometheus + Grafana    کامل با alerting و
                          ساده                    dashboards

  **تست**                 Unit + Integration      ۱۲ لایه آزمون کامل
                          (حداقل ۸۰٪)             

  **CI/CD**               Basic pipeline          کامل با staging،
                                                  canary، rollback

  **Risk Engine**         ساده --- Fixed          ۸ سطح با ATR-based
                          Fractional              sizing

  **Decision Journal**    ساده --- ثبت تصمیمات    با Feedback Loop ۳۰/۹۰
                                                  روزه

  **Compliance**          Disclaimer + IP check   کامل با KYC/AML،
                                                  Sanctions screening

  **Docker Network**      یک شبکه                 Paper/Live جدا شده
  -----------------------------------------------------------------------

#### اصول MVP-0:

1.  **یک صرافی، یک کاربر، یک استراتژی ساده** --- ابتدا این را به تولید
    برسان، بعد مقیاس بده
2.  **هیچ ML، هیچ Go، هیچ Multi-tenancy** --- این پیچیدگی‌ها برای MVP
    زودرس است
3.  **Paper Trading در Docker Network مجزا** --- حتی باگ نتواند سفارش
    واقعی ثبت کند
4.  **تمام تصمیمات با قواعد قطعی (deterministic)** --- نه مدل‌های آماری
    یا ML
5.  **Kill Switch از روز اول** --- مستقل و قابل تست

#### معیار موفقیت MVP-0:

-   [ ] یک کاربر می‌تواند سیگنال دریافت و تأیید کند
-   [ ] سفارش در Paper Trading (شبیه‌سازی) اجرا می‌شود
-   [ ] Risk Engine سفارش‌های پرریسک را رد می‌کند
-   [ ] Kill Switch قابل فعال‌سازی است
-   [ ] Audit Trail تمام تصمیمات را ثبت می‌کند
-   [ ] پوشش تست ≥ ۸۰٪ برای منطق ریسک

------------------------------------------------------------------------

## ۲. معماری سیستم و انتخاب Stack فناوری

### ۲.۱ تصمیم نهایی Stack فناوری (اصلاح نسخه ۴.۱)

> **پاسخ به نقد #۱ تیم فنی:** «هزینه تیم برای نگهداری دو زبان همزمان
> بالاست. برای یک MVP اولیه، این پیچیدگی زودهنگام (Premature
> Optimization) است.»

**تصمیم نهایی (اصلاح‌شده):** Python-only برای MVP-0. Go به post-MVP موکول
شد.

  ------------------------------------------------------------------------
  لایه               فناوری            فاز               دلیل
  ------------------ ----------------- ----------------- -----------------
  **تمام لایه‌ها      Python 3.12 +     MVP-0             اکوسیستم غنی،
  (MVP-0)**          FastAPI                             توسعه سریع، تیم
                                                         آشناتر

  **Market Data      Go (اختیاری)      Post-MVP با ADR   فقط اگر profiling
  Ingestion                                              نشان داد Python
  (Post-MVP)**                                           ناکافی است

  **پایگاه داده**    PostgreSQL 16     MVP-0: plain      
                     (MVP-0: plain     PostgreSQL کافی   
                     tables + index) → برای ۳ جفت ارز،   
                     TimescaleDB       TimescaleDB در    
                     (Post-MVP)        Post-MVP          

  **Cache و Event    Redis 7           MVP-0             Streams، lock،
  Bus**                                                  rate limit

  **مدیریت Secret**  Encrypted .env +  MVP-0: encrypted  
                     OS keyring        .env کافی، Vault  
                     (MVP-0) →         به Post-MVP موکول 
                     HashiCorp Vault   شد                
                     (Post-MVP)                          

  **Deployment**     Docker + Docker   MVP-0             Container
                     Compose                             isolation

  **Monitoring**     Prometheus +      MVP-0             Metrics،
                     Grafana                             dashboards

  **Notification**   Telegram Bot      MVP-0             دسترسی آسان در
                                                         ایران

  **Logging**        structlog (JSON)  MVP-0             Query آسان،
                                                         observability
  ------------------------------------------------------------------------

**قانون فیزی (قابل‌مذاکره نیست):** - **MVP-0:** تمام سرویس‌ها با
Python/FastAPI. هیچ کد Go وجود ندارد. - **Post-MVP:** Go فقط برای Market
Data Ingestion و Execution Adapter، پس از ثبت ADR و contract tests. -
**هیچ‌گاه:** منطق کسب‌وکار (risk، sizing، portfolio، signal engine) در Go
نوشته نمی‌شود. - **مرز تصمیم نهایی:** در MVP-0، Risk Engine (Python)
تصمیم نهایی را می‌گیرد. هیچ لایه دیگری نمی‌تواند سفارش را تأیید کند.

**Trade-off:** - مزیت MVP-0: یک زبان، یک تیم، توسعه سریع، هزینه پایین -
هزینه Post-MVP: پیچیدگی دو زبان فقط زمانی پذیرفته می‌شود که profiling آن
را توجیه کند - مرجع: مقایسه Python و Go برای معامله‌گری الگوریتمی نشان
می‌دهد Python برای MVP و research مناسب است، Go برای production execution
زمانی که latency حیاتی می‌شود
([LuxAlgo](https://www.luxalgo.com/blog/best-programming-languages-for-algorithmic-trading/)،
[QuantStart](https://www.quantstart.com/articles/Best-Programming-Language-for-Algorithmic-Trading-Systems/))

### ۲.۲ دیاگرام معماری

    ┌─────────────────────────────────────────────────────────────────┐
    │                    کاربران (Users)                                │
    │              تریدرها │ سرمایه‌گذاران │ مدیران سیستم                │
    └─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                   داشبورد یکپارچه (Unified Dashboard)             │
    │              Frontend: React │ Backend: FastAPI (Python)                │
    │                   PWA / Responsive (Mobile-first)               │
    └─────────────────────────────────────────────────────────────────┘
                                  │
            ┌─────────────────────┴─────────────────────┐
            │                                           │
            ▼                                           ▼
    ┌───────────────────────┐               ┌───────────────────────┐
    │  سیستم سیگنال‌دهی     │               │  سیستم مدیریت سبد     │
    │  Signal Trading       │               │  Portfolio Management │
    │  System (Python)      │               │  System (Python)      │
    └───────────────────────┘               └───────────────────────┘
            │                                           │
            └─────────────────────┬─────────────────────┘
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                     لایه‌های مشترک (Shared Layers)                │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
    │  │  Data Layer  │  │ Risk Engine  │  │Security Layer│          │
    │  │  (Python)    │  │  (Python)    │  │  (Python)    │          │
    │  │ - PostgreSQL │  │ - Position   │  │ - Bearer API │          │
    │  │ - Redis      │  │   Sizing     │  │   Key        │          │
    │  │ - Connectors │  │ - Portfolio  │  │ - OS Keyring │          │
    │  │              │  │   Heat       │  │ - Audit Log  │          │
    │  │              │  │ - Circuit    │  │ - RBAC       │          │
    │  │              │  │   Breaker    │  │              │          │
    │  └──────────────┘  └──────────────┘  └──────────────┘          │
    └─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                  زیرساخت خارجی (External Infrastructure)          │
    │    صرافی‌ها (Wallex، Binance) │ داده‌های بازار │ APIs            │
    └─────────────────────────────────────────────────────────────────┘

> **تغییر نسخه ۴.۱:** تمام لایه‌ها Python هستند. Go در این دیاگرام وجود
> ندارد.

------------------------------------------------------------------------

## ۳. لایه‌های مشترک (Shared Layers)

### ۳.۱ لایه داده (Data Layer)

#### وظایف اصلی:

-   دریافت داده از منابع مختلف (صرافی‌ها، داده‌های on-chain)
-   کنترل کیفیت داده (Data Quality Check)
-   نرمال‌سازی و ذخیره‌سازی

#### کنترل کیفیت داده:

``` python
class DataQualityChecker:
    def __init__(self, max_age_seconds: int = 5):
        self.max_age_seconds = max_age_seconds
    
    def check_data_quality(self, data: Dict, expected_symbols: list) -> Dict:
        quality_score = 1.0
        issues = []
        
        if 'timestamp' in data:
            data_age = datetime.now() - datetime.fromisoformat(data['timestamp'])
            if data_age.total_seconds() > self.max_age_seconds:
                quality_score -= 0.3
                issues.append(f"Stale data: {data_age.total_seconds()}s old")
        
        required_fields = ['open', 'high', 'low', 'close', 'volume']
        missing_fields = [f for f in required_fields if f not in data or data[f] is None]
        if missing_fields:
            quality_score -= 0.3
            issues.append(f"Missing fields: {missing_fields}")
        
        if 'high' in data and 'low' in data:
            if data['high'] < data['low']:
                quality_score -= 0.5
                issues.append("Invalid price: high < low")
        
        return {
            'quality_score': max(0.0, quality_score),
            'issues': issues,
            'is_usable': quality_score > 0.5
        }
```

### ۳.۲ موتور ریسک (Risk Engine)

#### وظایف اصلی:

-   محاسبه سایز پوزیشن (تفصیل در بخش ۵)
-   بررسی Portfolio Heat
-   کنترل‌های Pre-Trade
-   Circuit Breaker

### ۳.۳ لایه امنیت (Security Layer)

#### مدیریت Secret:

-   **MVP-0:** Encrypted `.env` + OS keyring (cryptography.fernet) ---
    کافی برای تیم ۱-۲ نفره. Vault به Post-MVP موکول شد
-   **Post-MVP / Production:** HashiCorp Vault با HSM/KMS backend برای
    کلیدهای API صرافی
-   کلیدهای API بدون دسترسی withdrawal
-   IP allowlisting
-   Rotation دوره‌ای کلید (هر ۹۰ روز در Post-MVP)

> **تغییر نسخه ۴.۱:** در production، در صورت امکان signing به Vault
> Transit/HSM/KMS واگذار می‌شود؛ در غیر این صورت secret فقط در scope
> کوتاه‌عمر decrypt شده و هرگز persist/log نمی‌شود. Vault با HSM یا cloud
> KMS (AWS KMS، Azure Key Vault) به‌عنوان managed key backend استفاده
> می‌شود ([HashiCorp Vault Managed
> Keys](https://developer.hashicorp.com/vault/docs/enterprise/managed-keys)‌).

#### RBAC (Role-Based Access Control):

  نقش            دسترسی
  -------------- --------------------------------
  **Viewer**     فقط خواندن dashboard و گزارش‌ها
  **Operator**   مشاهده + تأیید manual actions
  **Admin**      همه + تغییر پیکربندی
  **System**     اجرای خودکار (bot process)

#### Two-Person Approval برای:

-   تغییر risk limits
-   فعال‌سازی live trading (feature flag)
-   افزایش سرمایه درگیر
-   افزودن سیمبل جدید به live trading
-   غیرفعال‌سازی kill switch

### ۳.۴ Adapter Pattern (Exchange Abstraction)

``` python
class ExchangeAdapter(ABC):
    @abstractmethod
    def get_ticker(self, symbol: str) -> Ticker: ...
    
    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[OHLCV]: ...
    
    @abstractmethod
    def get_order_book(self, symbol: str, depth: int) -> OrderBook: ...
    
    @abstractmethod
    def place_order(self, symbol: str, side: str, order_type: str,
                    quantity: float, price: Optional[float] = None,
                    client_order_id: str = None) -> Order: ...
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool: ...
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatus: ...
```

**Implementations:** - `WallexAdapter` --- Wallex Spot API -
`BinanceAdapter` --- Binance Spot API - `BacktestAdapter` --- شبیه‌سازی
برای بک‌تست - `PaperTradingAdapter` --- شبیه‌سازی با داده زنده (در Docker
Network مجزا)

------------------------------------------------------------------------

## ۴. سیستم سیگنال‌دهی و قواعد تولید سیگنال

### ۴.۱ تایم‌فریم و جلوگیری از Look-Ahead Bias

-   **تایم‌فریم پایه:** کندل یک‌ساعته برای ساخت سیگنال ورود و محاسبه
    ATR(14)؛ کندل چهارساعته برای فیلتر جهت روند
-   **قانون طلایی:** همه اندیکاتورها با کندل‌های **بسته‌شده** محاسبه
    می‌شوند.

### ۴.۲ الگوهای ورود با تأیید چندلایه (Confluence)

#### الگوی ۱: Trend Following (خرید در روند صعودی)

  -----------------------------------------------------------------------
  لایه              اندیکاتور / شرط   مقدار             نقش
  ----------------- ----------------- ----------------- -----------------
  **لایه ۱: فیلتر   EMA(50) و         EMA(50) \>        اطمینان از روند
  روند**            EMA(200) در تایم  EMA(200)          صعودی کلان
                    ۴ساعته                              

  **لایه ۲: موقعیت  قیمت بسته‌شدن در   Close \> EMA(20)  تأیید مومنتوم
  قیمت**            تایم ۱ساعته                         کوتاه‌مدت

  **لایه ۳: شکست    بیشینه ۲۰ کندل    Close \> High(20) شکست مقاومت با
  معتبر**           پیشین + حجم       و Volume ≥ 1.5 ×  حجم تأییدشده
                                      AvgVolume(20)     
  -----------------------------------------------------------------------

#### الگوی ۲: Mean Reversion (بازگشت به میانگین در رنج)

  -----------------------------------------------------------------------
  لایه              اندیکاتور / شرط   مقدار             نقش
  ----------------- ----------------- ----------------- -----------------
  **لایه ۱: اشباع   RSI(14) در تایم   RSI \< 30 سپس     شناسایی نقطه
  فروش**            ۱ساعته            عبور به بالای 30  بازگشت مومنتوم

  **لایه ۲: موقعیت  Bollinger         Close ≤ Lower     تأیید انحراف شدید
  در باند**         Bands(20, 2)      Band سپس بازگشت   از میانگین
                                      به داخل           
  -----------------------------------------------------------------------

### ۴.۳ ساختار داده سیگنال

``` json
{
  "signal_id": "SIG-20251004-BTC-001",
  "symbol": "BTC/USDT",
  "direction": "LONG",
  "timestamp_utc": "2025-10-04T14:00:00Z",
  "rule_version": "4.1",
  "reference_price": 62450.00,
  "entry_range_min": 62400.00,
  "entry_range_max": 62500.00,
  "validity_minutes": 5,
  "data_quality_score": 0.98,
  "stop_loss_price": 61800.00,
  "take_profit_price": 63750.00,
  "risk_reward_ratio": 2.1,
  "suggested_position_size_usdt": 375.00,
  "invalidation_conditions": ["price_below_61750", "regime_change_to_bearish_4h"],
  "mode": "DIRECT" | "SIGNAL_ONLY",
  "approval_required": true,
  "max_slippage_pct": 0.3,
  "fee_estimate_pct": 0.4,
  "slippage_estimate_pct": 0.05,
  "position_sizing_method": "risk_budget_volatility",
  "atr_multiplier_sl": 1.5,
  "trailing_stop_multiplier": 2.5,
  "scaling_out_enabled": true,
  "confidence_score": 0.82,
  "uncertainty_budget": 0.18,
  "explanation": {
    "entry_reason": "EMA50>EMA200 (4h uptrend) + breakout above 20-bar high with 1.8x volume",
    "risk_reason": "Stop at 2x ATR (61800), R/R = 2.1, risk = 0.5% equity",
    "confluence_score": 3,
    "regime": "trending_up"
  }
}
```

> **تغییر نسخه ۴.۱:** فیلد `explanation` اضافه شد (پاسخ به پیشنهاد ب تیم
> فنی --- Visual Audit UI).

------------------------------------------------------------------------

## ۵. الگوریتم‌های مدیریت ریسک و Position Sizing

### ۵.۱ متدولوژی دقیق Position Sizing

**تصمیم نهایی:** رویکرد ترکیبی سه‌لایه --- Risk-Budget First → Volatility
Targeting Second → Hard Caps Third

#### لایه ۱: Risk-Budget (مبنای محاسبه)

``` python
# Step 1: Risk-Budget Base
risk_amount_usdt = account_equity × risk_fraction_per_trade
# risk_fraction: 0.5% (Trending), 0.3% (Range), 0.25% (High-Vol), 0% (Extreme)

# Step 2: Stop Distance (ATR-based, in price terms)
stop_distance_price = ATR(14) × volatility_multiplier
# multiplier: 2.0 (Trending), 1.5 (Range), 3.0 (High-Vol)

# Step 3: Effective stop distance including fees and slippage (in USDT terms)
effective_stop_distance_usdt = stop_distance_price + (entry_price × (fee_round_trip_pct + slippage_pct))

# Step 4: Quantity based on risk budget (in asset units)
qty_risk = risk_amount_usdt / effective_stop_distance_usdt

# Step 5: Notional value of position (in USDT)
notional_risk = qty_risk × entry_price
```

#### لایه ۲: Volatility Targeting

``` python
target_vol = 0.15  # 15% annual
asset_vol = annualized_volatility(returns_30d)
vol_weight = (target_vol / asset_vol) × confidence_multiplier
adjusted_notional = notional_risk × min(vol_weight, 1.0)
```

#### لایه ۳: Hard Caps

``` python
final_notional = min(
    adjusted_notional,
    account_equity × 0.15,                    # Max weight per asset: 15%
    portfolio_value × 0.70 × available_capital,  # Max total exposure: 70%
    daily_volume_24h × 0.01,                  # Max 1% of 24h volume
    max_position_size_user_setting             # User-defined cap (USDT)
)

# Liquidity check
if final_notional > order_book_depth_at_0.5pct × 0.10:
    final_notional = order_book_depth_at_0.5pct × 0.10

final_qty = final_notional / entry_price
```

#### فرمول نهایی Position Sizing

\[ `\text{Notional}`{=tex} =
`\min`{=tex}`\left`{=tex}(`\frac{E \times R_f}{\text{ATR}_{14} \times M_v + E_p \times (F_{rt} + S_{est})}`{=tex}
`\times`{=tex}E_p,; `\text{Notional}`{=tex}*{risk}
`\times`{=tex}`\min`{=tex}!`\left`{=tex}(`\frac{T_v}{\sigma_a}`{=tex}, 1.0`\right`{=tex}),;
E `\times 0.15`{=tex},; V*{24h} `\times 0.01`{=tex}`\right`{=tex}) \]

\[ `\text{Quantity}`{=tex} = `\frac{\text{Notional}}{E_p}`{=tex} \]

که در آن: - (E) = Account Equity (USDT)، (R_f) = Risk Fraction
(0.25%-0.5%) - (`\text{ATR}`{=tex}*{14}) = ATR (14 period)، (M_v) =
Volatility Multiplier (1.5-3.0) - (E_p) = Entry Price، (F*{rt}) = Fee
Round-Trip (0.4%)، (S\_{est}) = Slippage (0.3%-0.5% for Wallex/Nobitex؛
0.05% for Binance) - (T_v) = Target Volatility (15% annualized)،
(`\sigma`{=tex}*a) = Annualized volatility of asset (30-day rolling) -
(`\text{Notional}`{=tex}*{risk}) = Notional از لایه ۱ (Risk-Budget) -
Volatility Targeting فقط زمانی معنا دارد که (`\sigma`{=tex}*a) نوسان
سالانه‌شده باشد. اگر نوسان روزانه محاسبه شده، باید ابتدا با
(`\sigma`{=tex}*{daily} `\times`{=tex}`\sqrt{365}`{=tex}) به سالانه
تبدیل شود. - (V\_{24h}) = 24-hour volume of asset (USDT)

#### Kelly Criterion (اختیاری --- فقط پس از داده کافی)

> **هشدار:** Kelly کامل بسیار تهاجمی است. در عمل از **Fractional Kelly**
> (Quarter Kelly = ۲۵٪) استفاده می‌شود
> ([LBank](https://www.lbank.com/explore/mastering-the-kelly-criterion-for-smarter-crypto-risk-management)‌،
> [Bitcoin
> Foundation](https://bitcoinfoundation.org/news/trading/how-to-build-a-profitable-crypto-portfolio/)‌).

#### تنظیم بر اساس رژیم بازار

  رژیم                      ATR Multiplier   Risk Fraction   Max Exposure
  ------------------------- ---------------- --------------- --------------
  Trending (ADX \> 25)      2.0              0.5%            70%
  Range-bound (ADX \< 20)   1.5              0.3%            60%
  High-Volatility           3.0              0.25%           40%
  Extreme Event             ---              0%              20%

### ۵.۲ الگوریتم‌های Stop Loss و Take Profit

#### Stop Loss (ATR-based):

\[ `\text{Stop Loss (Long)}`{=tex} = `\text{Entry}`{=tex} -
(`\text{ATR}`{=tex} `\times`{=tex}`\text{Multiplier}`{=tex}) \]

  نوع دارایی      Multiplier
  --------------- -----------------
  BTC/ETH         1.5 - 2.0 × ATR
  Altcoins بزرگ   2.0 - 2.5 × ATR
  Altcoins کوچک   2.5 - 3.0 × ATR

#### Synthetic Stop-Loss برای صرافی‌های داخلی (پاسخ به اشکال P0 #۲)

> **اشکال تیم فنی:** «والکس و نوبیتکس از OCO/Stop-Loss بومی در API
> پشتیبانی پایدار ندارند. اگر سرور قطع بشه، اینترنت بره، یا Flash Crash
> شبانه اتفاق بیفته --- سفارش استاپ در صرافی وجود نداره و پوزیشن بدون
> هیچ محافظی باز می‌مونه."

**مشکل:** صرافی‌های داخلی ایران (Wallex، Nobitex) از سفارش‌های OCO یا
Stop-Loss بومی در API پشتیبانی نمی‌کنند یا پشتیبانی پایدار ندارند. این
یعنی اگر سرور ربات قطع شود، استاپ‌لاس در صرافی ثبت نشده و پوزیشن بدون
محافظ باز می‌ماند.

**راهکار: Client-side Synthetic Stop با Polling فعال**

``` python
class SyntheticStopLossManager:
    """Client-side synthetic stop-loss for exchanges without native OCO support."""
    
    POLL_INTERVALS = {
        '1H': 30,    # seconds
        '4H': 60,    # seconds
        '1D': 300,   # seconds (5 min)
    }
    
    def __init__(self, exchange_adapter, kill_switch):
        self.exchange = exchange_adapter
        self.kill_switch = kill_switch
        self.active_stops = {}  # position_id -> stop_info
        
    async def monitor_positions(self):
        """Main polling loop - checks all active positions against their stops."""
        while True:
            for pos_id, stop_info in self.active_stops.items():
                try:
                    current_price = await self.exchange.get_ticker(stop_info['symbol'])
                    
                    # Check if stop-loss is triggered
                    if stop_info['side'] == 'LONG' and current_price <= stop_info['stop_price']:
                        await self.execute_synthetic_stop(pos_id, stop_info)
                    elif stop_info['side'] == 'SHORT' and current_price >= stop_info['stop_price']:
                        await self.execute_synthetic_stop(pos_id, stop_info)
                        
                except ConnectionError:
                    # Server/network down - IMMEDIATE alert + Kill Switch
                    await self.handle_connection_failure(pos_id, stop_info)
                    
            interval = self.POLL_INTERVALS.get(self.current_timeframe, 30)
            await asyncio.sleep(interval)
    
    async def execute_synthetic_stop(self, pos_id, stop_info):
        """Execute stop-loss by placing a market order."""
        try:
            await self.exchange.place_order(
                symbol=stop_info['symbol'],
                side='SELL' if stop_info['side'] == 'LONG' else 'BUY',
                order_type='MARKET',
                quantity=stop_info['quantity']
            )
            await self.notify_user(f"Stop-loss executed for {pos_id} at market price")
        except Exception:
            # If market order fails - activate Kill Switch
            await self.kill_switch.activate(
                reason=f"Synthetic stop-loss failed for {pos_id}"
            )
    
    async def handle_connection_failure(self, pos_id, stop_info):
        """Handle server/network outage while positions are open."""
        # 1. Immediate alert via multiple channels
        await self.notify_user(
            severity='CRITICAL',
            message=f"CONNECTION LOST while position {pos_id} is open. "
                    f"Stop-loss at {stop_info['stop_price']}. "
                    f"Manual intervention required."
        )
        # 2. Auto-activate Kill Switch (prevent new trades)
        await self.kill_switch.activate(
            reason=f"Connection lost with active positions - {pos_id}"
        )
        # 3. Retry connection with exponential backoff
        for attempt in range(5):
            await asyncio.sleep(min(30 * (attempt + 1), 300))  # 30, 60, 90, 120, 150s
            try:
                current_price = await self.exchange.get_ticker(stop_info['symbol'])
                # Re-check stop
                if stop_info['side'] == 'LONG' and current_price <= stop_info['stop_price']:
                    await self.execute_synthetic_stop(pos_id, stop_info)
                return
            except ConnectionError:
                continue
        # All retries failed - notify admin for manual intervention
        await self.notify_admin(f"All retries failed for {pos_id}. Manual intervention required.")
```

#### قواعد Synthetic Stop-Loss:

  ---------------------------------------------------------------------
  قانون                              توضیح
  ---------------------------------- ----------------------------------
  ۱. Polling فعال                    هر ۳۰-۳۰۰ ثانیه (بسته به تایم‌فریم)
                                     وضعیت پوزیشن بررسی می‌شود

  ۲. قطعی ارتباط                     هشدار فوری (Telegram/SMS) + Kill
                                     Switch خودکار

  ۳. تلاش مجدد                       ۵ تلاش با exponential backoff
                                     (۳۰-۱۵۰ ثانیه)

  ۴. شکست کامل                       notify admin برای مداخله دستی

  ۵. محدودیت مستندسازی               این محدودیت در Runbook صرافی داخلی
                                     مستند شده است
  ---------------------------------------------------------------------

> **هشدار عملیاتی:** Synthetic Stop-Loss یک راهکار جایگزین برای صرافی‌های
> بدون OCO بومی است، اما در صورت قطعی طولانی‌مدت ارتباط یا ریزش شدید
> بازار، تضمین نمی‌کند که استاپ دقیقاً در قیمت مشخص اجرا شود. این محدودیت
> باید در ریسک‌های سیستم مستند شود.

#### Take Profit (Scaling Out):

  مرحله    درصد پوزیشن   سطح هدف
  -------- ------------- --------------------------
  TP1      40%           1.5R - 2R
  TP2      35%           2.5R - 3R
  Runner   25%           Trailing Stop (2.5× ATR)

### ۵.۳ Maximum Drawdown Protection

  Drawdown            اقدام
  ------------------- ----------------------
  روزانه 2%           توقف معاملات روز
  هفتگی 5%            کاهش exposure به 30%
  8% (Soft)           کاهش exposure به 50%
  12% (Hard)          توقف معاملات جدید
  15% (Kill Switch)   بستن همه پوزیشن‌ها

------------------------------------------------------------------------

## ۶. سیستم مدیریت سبد (Portfolio Management)

### ۶.۱ موتور تحلیل چندعاملی

  عامل          وزن پیش‌فرض   توضیح
  ------------- ------------ ---------------------------------
  Fundamental   30%          تحلیل بنیادی پروژه، تیم، فناوری
  Technical     25%          تحلیل تکنیکال، روند، مومنتوم
  On-Chain      20%          فعالیت زنجیره‌ای، انتقال‌ها
  Liquidity     15%          نقدشوندگی، حجم، spread
  Sentiment     10%          احساسات بازار

### ۶.۲ موتور تخصیص سرمایه

-   **Baseline:** Equal Weight (1/N)
-   **پیشرفته:** Inverse Volatility (weight ∝ 1/σ)
-   **بازمتوازن‌سازی:** هر ۷ روز + ۵٪ انحراف
-   **حداکثر turnover:** ۳۰٪ per rebalance

### ۶.۳ Universe Selection

-   تعداد دارایی: ۱۰-۱۵ سکه نقدشونده
-   حداقل حجم روزانه: ۱۰M USDT
-   Max وزن تک‌دارایی: 15%

------------------------------------------------------------------------

## ۷. چرخه تأیید، اجرا و حفاظت

### ۷.۱ چرخه وضعیت سفارش

    SIGNAL_CREATED → PENDING_APPROVAL → (APPROVED | REJECTED | EXPIRED)
    → PRE_TRADE_VALIDATION → SUBMITTED → PARTIALLY_FILLED → FILLED
    → PROTECTED (SL/TP Registered) | PROTECTION_FAILED
    → TP1_HIT → TP2_HIT → TRAILING_ACTIVE → CLOSED | CANCELLED

### ۷.۲ اعتبارسنجی پیش از ارسال (Pre-Trade Validation)

  بررسی         شرط عبور                           اقدام در صورت شکست
  ------------- ---------------------------------- ----------------------
  تازگی داده    ≤ ۵ ثانیه                          توقف ارسال
  اختلاف قیمت   ≤ 0.3%                             ابطال و درخواست مجدد
  نقدشوندگی     Spread ≤ 0.10%                     رد سفارش
  موجودی        ≥ Position Size + Fees             کاهش یا رد
  Idempotency   عدم وجود تکرار در ۵ دقیقه          جلوگیری از تکرار
  Risk Layer    تأیید با max_size و reason_codes   رد
  انقضا         expiry_at \> now                   رد و EXPIRED

### ۷.۳ مدیریت Fill جزئی و حفاظت

-   **Fill جزئی:** حفاظت فوراً برای مقدار پرشده. باقیمانده حداکثر ۶۰
    ثانیه منتظر.
-   **ثبت SL/TP:** پس از Fill الزامی. شکست → تلاش مجدد (۳ بار)، هشدار،
    توقف.
-   **Idempotency Key:** هر سفارش با client-side order ID منحصربه‌فرد.

------------------------------------------------------------------------

## ۸. Conflict Resolution و اولویت‌بندی سیگنال‌ها

### ۸.۱ سلسله‌مراتب تصمیم‌گیری (Rule-Based)

    Priority 1: IPS / User Policy Override (بالاترین اولویت)
        ↓
    Priority 2: Risk Engine Veto (مستقل از سیگنال)
        ↓
    Priority 3: Long-Term Allocation Drift Rules
        ↓
    Priority 4: Short-Term Signal (Trend/MR)
        ↓
    Priority 5: Sentiment / Auxiliary Signals

### ۸.۲ قواعد Conflict Resolution

``` python
def resolve_conflict(signal_short_term, allocation_long_term, ips, risk_state):
    # Rule 1: IPS Override
    if not ips.allows(signal_short_term.symbol, signal_short_term.side):
        return Decision.REJECT, "IPS does not allow this asset/side"
    
    # Rule 2: Risk Engine Veto
    if risk_state.daily_loss_exceeded or risk_state.drawdown_hard:
        return Decision.REJECT, "Risk limits exceeded"
    
    # Rule 3: Long-term allocation drift
    current_weight = allocation_long_term.get_weight(signal_short_term.symbol)
    target_weight = allocation_long_term.get_target_weight(signal_short_term.symbol)
    drift = abs(current_weight - target_weight)
    
    if signal_short_term.direction == "LONG" and target_weight < current_weight:
        if drift > 0.05:
            return Decision.REJECT, "Long-term requires reduction"
        else:
            signal_short_term.size *= 0.5
            return Decision.APPROVE_REDUCED, "Size reduced due to direction conflict"
    
    # Rule 4: Signal confidence
    if signal_short_term.confidence < 0.6:
        return Decision.REJECT, "Confidence below threshold"
    
    # Rule 5: Data quality
    if signal_short_term.data_quality_score < 0.8:
        return Decision.REJECT, "Data quality below threshold"
    
    # Rule 6: Liquidity
    if not liquidity_check(signal_short_term.symbol, signal_short_term.size):
        return Decision.REJECT, "Liquidity check failed"
    
    # Rule 7: Compliance
    if not compliance_check(signal_short_term.symbol):
        return Decision.REJECT, "Compliance check failed"
    
    return Decision.APPROVE, "All checks passed"
```

### ۸.۳ قواعد ابطال سیگنال

-   تغییر رژیم بازار
-   پایان مهلت انقضا
-   داده نامعتبر (Stale Data \> ۵ ثانیه)
-   نقض Conflict Resolution
-   فعال‌سازی Kill Switch

------------------------------------------------------------------------

## ۹. کیفیت، آزمون و دروازه‌های مرحله‌ای

### ۹.۱ لایه‌های آزمون (۱۲ لایه)

  -----------------------------------------------------------------------
  لایه              نوع               پوشش              معیار
  ----------------- ----------------- ----------------- -----------------
  ۱                 Unit Test         توابع محاسباتی،   ≥ ۹۰٪ برای منطق
                                      sizing، ATR       ریسک

  ۲                 Integration Test  DB، Redis،        تمام endpoints
                                      Exchange API      
                                      (mock)            

  ۳                 Property-Based    Invariants ریسک   ۱۰۰۰ اجرای تصادفی
                    Test                                

  ۴                 State Machine     چرخه وضعیت سفارش  تمام transitions
                    Test                                

  ۵                 Contract Test     API contract بین  تمام contract‌ها
                                      سرویس‌ها           

  ۶                 Backtest          Walk-forward      Sharpe OOS ≥ 50٪
                    Validation                          IS

  ۷                 Paper Trading     شبیه‌سازی با داده  حداقل ۱۰۰ معامله
                    Test              زنده              

  ۸                 Failure Injection Circuit breaker،  fail-closed
                                      stale data        

  ۹                 Security Test     RBAC، audit،      بدون critical CVE
                                      secret            

  ۱۰                Performance Test  Latency،          p99 \< 200ms
                                      throughput        

  ۱۱                Reconciliation    Balance، order،   ۱۰۰٪ تطابق
                    Test              position          

  ۱۲                Chaos Engineering Kill process،     بازیابی در ۶۰
                                      network partition ثانیه
  -----------------------------------------------------------------------

### ۹.۲ دروازه‌های اجرایی (G0 تا G7)

  دروازه   مرحله          معیار پذیرش
  -------- -------------- -----------------------------------------
  G0       پیش از شروع    ADR‌ها تأیید شده، ساختار پروژه ایجاد شده
  G1       زیرساخت        Docker اجرا می‌شود، migrations موفق
  G2       لایه داده      داده real-time، Quality \> 0.95
  G3       موتور ریسک     sizing صحیح، رد پرریسک
  G4       سیستم سیگنال   تولید سیگنال، تأیید صریح
  G5       مدیریت سبد     امتیازدهی، تخصیص
  G6       داشبورد        نمایش همزمان، گزارش‌ها
  G7       تولید          uptime \> 99.5٪، p99 \< 200ms

### ۹.۳ اصل توسعه بر مبنای Feature Flag

-   هیچ قابلیتی پیش از تکمیل و تست فعال نمی‌شود
-   `live_trading` flag پیش‌فرض `false` و immutable در Paper Trading محیط
-   فعال‌سازی `live_trading` نیاز به Two-Person Approval دارد

### ۹.۴ Chaos Engineering Checklist (پاسخ به پیشنهاد د)

> **پاسخ به پیشنهاد د تیم فنی:** «قبل از فاز E، حداقل یک تمرین Chaos
> ساده اجرا کن.»

#### قواعد کلی Chaos Engineering:

1.  **Blast Radius محدود:** هر آزمون فقط یک سرویس را تحت تأثیر قرار
    می‌دهد
2.  **Abort Conditions صریح:** اگر تأثیر از حد مجاز فراتر رفت، آزمون
    فوری متوقف شود
3.  **Approval از Risk Owner:** پیش از اجرا، تأیید مکتوب لازم است
4.  **Staging اول:** هرگز در production بدون staging test اجرا نشود
5.  **Reversibility:** تمام آزمون‌ها قابل rollback در کمتر از ۶۰ ثانیه

#### حداقل آزمون‌های Chaos (پیش از فاز E):

  ----------------------------------------------------------------------
  \#            آزمون         محیط          انتظار        نتیجه مطلوب
  ------------- ------------- ------------- ------------- --------------
  ۱             قطع Redis     Staging       سیستم به DB   NO_ACTION
                                            fallback      (معاملات
                                            می‌کند         متوقف،
                                                          fail-closed)

  ۲             قطع API صرافی Staging       Circuit       NO_ACTION
                                            Breaker فعال  (معاملات
                                                          متوقف)

  ۳             داده Stale    Staging       Stale Data    NO_ACTION
                (\> ۵ ثانیه)                Breaker فعال  

  ۴             Kill Process  Staging       Kill Switch   NO_ACTION
                (Signal                     فعال،         
                Engine)                     Watchdog      

  ۵             قطع شبکه      Staging       سیستم         NO_ACTION
                (Network                    fail-closed   
                Partition)                  می‌شود         

  ۶             DB Connection Staging       توقف کامل     NO_ACTION
                Loss                        معاملات       

  ۷             CPU/Memory    Staging       سیستم degrade Reduced
                Spike                       gracefully    exposure
  ----------------------------------------------------------------------

> **قانون کلیدی:** در تمام آزمون‌ها، سیستم باید به `NO_ACTION` برسد ---
> یعنی هیچ سفارش واقعی ثبت نشود و تمام پوزیشن‌ها حفظ شوند. اگر سیستم در
> هر آزمون به `NO_ACTION` نرسید، فاز E نباید شروع شود. مرجع: AWS Chaos
> Engineering Lifecycle
> ([AWS](https://docs.aws.amazon.com/prescriptive-guidance/latest/chaos-engineering-on-aws/lifecycle.html)‌،
> [Gremlin](https://www.gremlin.com/whitepapers/chaos-engineering-for-financial-services)‌).

#### زمان‌بندی اجرا:

-   **MVP-0:** آزمون‌های ۱ تا ۳ در Staging (قبل از Paper Trading)
-   **پیش از فاز E:** تمام ۷ آزمون در Staging
-   **Production (فصلی):** آزمون‌های محدود با blast radius کوچک

------------------------------------------------------------------------

## ۱۰. ورودی کاربر و سیاست سرمایه‌گذاری (IPS)

### ۱۰.۱ فیلدهای ورودی اجباری

  ------------------------------------------------------------------------
  فیلد                          نوع           توضیح          اعتبارسنجی
  ----------------------------- ------------- -------------- -------------
  `initial_capital`             decimal       سرمایه اولیه   \> 0، حداقل
                                              (USDT)         ۵۰۰ USDT

  `risk_profile`                enum          conservative / سازگار با
                                              moderate /     capital
                                              aggressive     

  `max_risk_per_trade`          float         درصد ریسک هر   0.25% - 1.0%
                                              معامله         

  `max_daily_loss`              float         حداقل زیان     1% - 3%
                                              روزانه         

  `max_portfolio_heat`          float         مجموع ریسک     1.5% - 6%
                                              پوزیشن‌ها       

  `max_drawdown_hard`           float         سقف Drawdown   10% - 15%

  `max_asset_weight`            float         حداکثر وزن     10% - 20%
                                              تک‌دارایی       

  `allowed_assets`              list          دارایی‌های مجاز ⊆ allowed
                                                             universe

  `investment_horizon`          enum          short / medium ---
                                              / long         

  `rebalance_frequency`         enum          daily / weekly ---
                                              / monthly      

  `rebalance_threshold`         float         آستانه انحراف  3% - 10%

  `max_total_exposure`          float         حداکثر         60% - 80%
                                              exposure       

  `min_cash_reserve`            float         حداقل ذخیره    10% - 20%
                                              نقدی           

  `approval_timeout_minutes`    int / null    سقف کاهنده مهلت تأیید  ۳-۲۴۰ دقیقه
                                              سیگنال         (پیش‌فرض: null؛
                                                               استفاده از Dynamic Timeout)

  `default_action_on_timeout`   enum          EXPIRE /       پیش‌فرض:
                                              REJECT         EXPIRE
  ------------------------------------------------------------------------

> **تغییر نسخه ۴.۱:** فیلدهای `approval_timeout_minutes` و
> `default_action_on_timeout` اضافه شد (پاسخ به پیشنهاد ز).

### ۱۰.۲ اعتبارسنجی و IPS Snapshot

``` python
@dataclass(frozen=True)
class InvestmentPolicySnapshot:
    version: int
    created_at: datetime
    initial_capital: Decimal
    risk_profile: RiskProfile
    max_risk_per_trade: float
    max_daily_loss: float
    max_portfolio_heat: float
    max_drawdown_hard: float
    max_asset_weight: float
    allowed_assets: List[str]
    investment_horizon: str
    rebalance_frequency: str
    rebalance_threshold: float
    max_total_exposure: float
    min_cash_reserve: float
    approval_timeout_minutes: Optional[int]  # 3-240; None => Dynamic Timeout
    default_action_on_timeout: str
    
    def validate(self) -> List[str]:
        errors = []
        if self.max_risk_per_trade > 0.01:
            errors.append("Risk per trade exceeds 1%")
        if self.max_daily_loss < self.max_risk_per_trade * 2:
            errors.append("Daily loss should be >= 2x risk per trade")
        if self.max_drawdown_hard < self.max_daily_loss * 3:
            errors.append("Hard drawdown should be >= 3x daily loss")
        if self.approval_timeout_minutes is not None:
            if self.approval_timeout_minutes < 3 or self.approval_timeout_minutes > 240:
                errors.append("Approval timeout cap must be 3-240 minutes or None")
        return errors
```

### ۱۰.۳ نسخه‌بندی سیاست

-   هر تغییر IPS نسخه جدید ایجاد می‌کند
-   پیشنهاد‌های قدیمی `STALE` علامت‌گذاری می‌شوند

------------------------------------------------------------------------

## ۱۱. مدیریت ریسک ۸ سطحی

### ۱۱.۱ سلسله‌مراتب ریسک

    Level 1: Kill Switch ← مستقل از همه ماژول‌ها
        ↓
    Level 2: کنترل Drawdown (Soft / Hard / Kill)
        ↓
    Level 3: محدودیت زیان روزانه و هفتگی
        ↓
    Level 4: محدودیت تمرکز دارایی
        ↓
    Level 5: محدودیت همبستگی و نقدشوندگی
        ↓
    Level 6: محدودیت استراتژی
        ↓
    Level 7: محدودیت سطح پوزیشن
        ↓
    Level 8: اعتبارسنجی سطح سفارش

### ۱۱.۲ پارامترهای پیش‌فرض

  پارامتر               مقدار بهینه   بازه
  --------------------- ------------- ------------
  Max ریسک هر معامله    0.5%          0.25% - 1%
  Max زیان روزانه       2%            1% - 3%
  Max Drawdown (Soft)   8%            6% - 10%
  Max Drawdown (Hard)   12%           10% - 15%
  Kill Switch           15%           12% - 20%
  Max وزن تک‌دارایی      15%           10% - 20%
  Max Exposure          70%           60% - 80%
  Min Cash Reserve      15%           10% - 20%

### ۱۱.۳ Kill Switch

Kill Switch باید مستقل از Signal Engine و Risk Engine باشد. یک فرآیند
جداگانه با watchdog timer.

**شرایط فعال‌سازی:** - Drawdown \> 15% - دستور دستی (Telegram command) -
Watchdog timeout (Risk Engine در ۶۰ ثانیه پاسخ ندهد) - DB connection
loss \> ۵ دقیقه - Exchange API down \> ۵ دقیقه

### ۱۱.۴ ماتریس اختیار Kill Switch (پاسخ به نقد #۷)

> **نقد تیم فنی:** «چه کسی می‌تواند Kill Switch را فعال کند؟ آیا کاربر
> می‌تواند override کند؟ تست دوره‌ای پیش‌بینی نشده.»

#### ماتریس اختیار (Activation Authority)

  -----------------------------------------------------------------------
  Actor             می‌تواند فعال کند  می‌تواند غیرفعال   توضیح
                                      کند               
  ----------------- ----------------- ----------------- -----------------
  **سیستم خودکار**  ✅ بله (Drawdown  ❌ نه             فعال‌سازی خودکار،
                    \> 15%، Watchdog                    غیرفعال‌سازی ممنوع
                    timeout)                            

  **کاربر (User)**  ✅ بله (Telegram  ❌ نه             کاربر می‌تواند
                    command)                            فعال کند اما
                                                        غیرفعال کردن نیاز
                                                        به approval دارد

  **Operator**      ✅ بله            ❌ نه (تنها با    غیرفعال‌سازی نیاز
                                      Two-Person        به Admin +
                                      Approval)         Operator تأیید

  **Admin**         ✅ بله            ✅ بله (با        فقط Admin می‌تواند
                                      Two-Person        resume کند، با
                                      Approval)         تأیید دوم
  -----------------------------------------------------------------------

#### قوانین Override:

1.  **کاربر نمی‌تواند Kill Switch را override کند:** اگر Kill Switch فعال
    است، هیچ سیگنالی قابل تأیید نیست
2.  **Resume فقط با Root-Cause Analysis:** قبل از غیرفعال‌سازی، دلیل
    فعال‌سازی باید مستند شود
3.  **Resume با Reduced Exposure:** پس از غیرفعال‌سازی، exposure به ۳۰٪
    کاهش می‌یابد و به‌تدریج بازمی‌گردد
4.  **Resume نیاز به Two-Person Approval دارد** (Admin + Operator)

#### Fire Drill (تست دوره‌ای Kill Switch):

  -----------------------------------------------------------------------
  نوع               محیط              فرکانس            توضیح
  ----------------- ----------------- ----------------- -----------------
  **Staging Fire    Staging           ماهانه            فعال‌سازی و تست
  Drill**                                               بازیابی

  **Paper Fire      Paper Trading     فصلی              فعال‌سازی در محیط
  Drill**                                               شبیه‌سازی

  **Production      Production        هرگز بدون         فقط در صورت
  Drill**                             شبیه‌سازی          آمادگی کامل تیم
  -----------------------------------------------------------------------

#### معیار پذیرش Fire Drill:

-   [ ] Kill Switch در کمتر از ۵ ثانیه فعال می‌شود
-   [ ] تمام پوزیشن‌ها در کمتر از ۳۰ ثانیه بسته می‌شوند
-   [ ] notification در کمتر از ۱۰ ثانیه ارسال می‌شود
-   [ ] audit log ثبت می‌شود
-   [ ] resume با reduced exposure کار می‌کند
-   [ ] Two-Person Approval برای resume کار می‌کند

------------------------------------------------------------------------

## ۱۲. نقشه راه پیاده‌سازی (بازنگری‌شده)

### ۱۲.۱ Roadmap با Team-Size Assumptions (پاسخ به نقد #۳)

> **نقد تیم فنی:** «فاز A تا G در ۲۰ هفته برای یک تیم کوچک بعید به نظر
> می‌رسد. هیچ‌جا تعداد توسعه‌دهنده، budget یا تعریف تیم مشخص نشده.»

#### فرضیات تیم:

  -----------------------------------------------------------------------
  سایز تیم          تعداد توسعه‌دهنده  زمان تخمینی MVP-0 زمان تخمینی
                                                        Production
  ----------------- ----------------- ----------------- -----------------
  **تیم کوچک**      ۱-۲ نفر           ۱۲-۱۶ هفته        ۹-۱۲ ماه

  **تیم متوسط**     ۳-۴ نفر           ۸-۱۰ هفته         ۶-۸ ماه

  **تیم بزرگ**      ۵+ نفر            ۶-۸ هفته          ۴-۶ ماه
  -----------------------------------------------------------------------

> **توضیح:** نقشه‌راه قبلی (نسخه ۴.۰) نقشه‌راه کل محصول بود، نه MVP. در
> نسخه ۴.۱، نقشه‌راه به دو بخش تقسیم شده: MVP-0 (حداقل محصول) و
> Production Grade (توسعه کامل).

#### نقشه‌راه MVP-0 (تیم کوچک: ۱-۲ نفر)

  -------------------------------------------------------------------------
  فاز            مدت            تحویلی‌ها                     معیار موفقیت
  -------------- -------------- ---------------------------- --------------
  **MVP-A:       هفته ۱-۳       \- PostgreSQL 16 (plain      تمام سرویس‌ها
  Foundation**                  tables +                     اجرا،
                                index)`<br>`{=html}-         migrations
                                Redis`<br>`{=html}-          موفق
                                Encrypted .env + OS          
                                keyring`<br>`{=html}- Docker 
                                Compose`<br>`{=html}- CI/CD  
                                ساده`<br>`{=html}-           
                                Single-tenant                

  **MVP-B:       هفته ۴-۶       \- یک Exchange               داده
  Data + Risk**                 Connector`<br>`{=html}- Data real-time،
                                Quality                      sizing صحیح
                                Checker`<br>`{=html}-        
                                Position Sizing (Fixed       
                                Fractional)`<br>`{=html}-    
                                Pre-Trade Checks             

  **MVP-C:       هفته ۷-۹       \- Signal Engine (Trend      تولید سیگنال،
  Signal +                      Following +                  تأیید صریح
  Approval**                    MR)`<br>`{=html}- Approval   
                                Queue`<br>`{=html}- Paper    
                                Trading Engine               

  **MVP-D: Paper هفته ۱۰-۱۶     \- Paper Trading در Docker   حداقل ۵۰
  Trading                       Network مجزا`<br>`{=html}-   معامله کاغذی
  (تمدید)**                     Walk-Forward                 موفق (MVP).
                                ساده`<br>`{=html}- Kill      برای live
                                Switch مستقل`<br>`{=html}-   controlled
                                Audit Trail                  execution:
                                                             حداقل ۱۰۰
                                                             معامله paper +
                                                             stress tests +
                                                             chaos tests

  **MVP-E:       هفته ۱۷-۲۰     \- Dashboard ساده            نمایش سیگنال و
  Dashboard**                   (Responsive)`<br>`{=html}-   پرتفو
                                Risk Metrics                 
                                display`<br>`{=html}- Audit  
                                Log display                  
  -------------------------------------------------------------------------

#### نقشه‌راه Production Grade (Post-MVP)

  ---------------------------------------------------------------------------
  فاز               مدت (تیم       تحویلی‌ها                    معیار موفقیت
                    متوسط)                                     
  ----------------- -------------- --------------------------- --------------
  **Prod-A:         ۴ هفته         \- RLS با Benchmark         p95 query
  Multi-tenancy**                  Gate`<br>`{=html}- Tenant   latency \<
                                   isolation                   50ms

  **Prod-B:         ۶ هفته         \- Shadow                   Baseline
  ML/JEV**                         Mode`<br>`{=html}- A/B      metrics پاس
                                   Testing`<br>`{=html}- JEV   شود
                                   (non-critical layers)       

  **Prod-C: Stress  ۳ هفته         \- Monte                    Max DD (95th)
  Testing**                        Carlo`<br>`{=html}- ۷       \< 15%
                                   سناریو                      

  **Prod-D: PWA**   ۴ هفته         \- PWA کامل`<br>`{=html}-   Lighthouse ≥
                                   Offline strategy            90

  **Prod-E: Live    ۶ هفته         \- Live Data                اجرای کنترل‌شده
  Integration**                    (read-only)`<br>`{=html}-   
                                   Sandbox                     
                                   execution`<br>`{=html}-     
                                   Reconciliation              

  **Prod-F:         ۴ هفته         \- K8s                      uptime \>
  Production**                     deployment`<br>`{=html}-    99.5%
                                   Full                        
                                   monitoring`<br>`{=html}-    
                                   Documentation               
  ---------------------------------------------------------------------------

### ۱۲.۲ تغییرات کلیدی نقشه راه

1.  **جداسازی MVP از Production:** MVP-0 فقط Python، single-user، یک
    صرافی
2.  **تمدید Paper Trading:** حداقل یک چرخه کامل نوسان بازار
3.  **فاز E به کنترل‌شده تقسیم شد:** ابتدا read-only + sandbox
4.  **Team-size assumptions صریح:** زمان‌بندی وابسته به سایز تیم

### ۱۲.۳ Paper Trading با Docker Network Isolation (پاسخ به نقد #۶ و پیشنهاد و)

> **نقد تیم فنی:** «Paper Trading روی همان زیرساخت تولید اجرا می‌شود. اگر
> یک باگ باعث ارسال سفارش واقعی بشه، هیچ لایه جداسازی شبکه‌ای تعریف
> نشده.»

#### معماری Docker Network Isolation:

``` yaml
# docker-compose.paper-trading.yml
version: '3.8'

networks:
  paper_network:
    driver: bridge
    internal: true  # No external access
  live_network:
    driver: bridge

services:
  paper-trading-bot:
    build: .
    networks:
      - paper_network
    environment:
      - LIVE_TRADING=false  # IMMUTABLE - cannot be overridden
      - DATABASE_URL=postgresql://paper_user:***@paper-db:5432/paper
      - REDIS_URL=redis://paper-redis:6379/0
    # NO access to live_network or external exchange endpoints
    
  paper-db:
    image: timescale/timescaledb:latest-pg16
    networks:
      - paper_network
    
  paper-redis:
    image: redis:7-alpine
    networks:
      - paper_network

  # Live trading bot - separate network
  live-trading-bot:
    build: .
    networks:
      - live_network
    profiles: ["live"]  # Only starts with explicit --profile live
    environment:
      - LIVE_TRADING=true
      - DATABASE_URL=postgresql://live_user:***@live-db:5432/live
```

#### قوانین جداسازی:

1.  **دو Docker Network مجزا:** `paper_network` و `live_network` --- هیچ
    ارتباطی بین آنها وجود ندارد
2.  **`LIVE_TRADING=false` immutable در Paper محیط:** این flag در کد
    به‌صورت hard-coded immutable است و نمی‌تواند با env override شود
3.  **Egress Deny:** `paper_network` با `internal: true` هیچ دسترسی به
    اینترنت خارجی ندارد. فقط به Paper Adapter (mock) متصل می‌شود
4.  **API Keys مجزا:** Paper محیط از API Key‌های واقعی صرافی استفاده
    نمی‌کند --- فقط Mock/Paper Adapter
5.  **Database مجزا:** Paper و Live روی دیتابیس‌های جداگانه هستند
6.  **Profile-based startup:** Live Trading فقط با `--profile live` شروع
    می‌شود --- اشتباهاً اجرا نمی‌شود

#### تضمین ایمنی:

``` python
# In code: LIVE_TRADING flag is read-only after startup
import os

class TradingMode:
    _instance = None
    _mode = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._mode = os.getenv('LIVE_TRADING', 'false').lower() == 'true'
            # Lock the value - cannot be changed at runtime
            cls._locked = True
        return cls._instance
    
    @property
    def is_live(self) -> bool:
        return self._mode
    
    def set_live(self, value: bool):
        if hasattr(self, '_locked') and self._locked:
            raise RuntimeError("LIVE_TRADING is immutable after startup")
        self._mode = value
```

> **مرجع:** Docker network isolation با `internal: true` تمام دسترسی
> خارجی را مسدود می‌کند. حتی اگر باگی وجود داشته باشد، کانتینر Paper
> نمی‌تواند به endpoint واقعی صرافی دسترسی پیدا کند ([Docker
> Docs](https://docs.docker.com/engine/network/)‌).

------------------------------------------------------------------------

## ۱۳. SLA، RTO و RPO و Operational Runbook

### ۱۳.۱ اهداف SLA

  ----------------------------------------------------------------------
  طبقه سرویس     Uptime هدف    RTO           RPO           مثال
  -------------- ------------- ------------- ------------- -------------
  **Critical     99.9%         5 دقیقه       ۱ دقیقه       Kill Switch،
  (Tier 1)**                                               Risk Engine

  **Important    99.5%         15 دقیقه      ۵ دقیقه       Signal
  (Tier 2)**                                               Engine، Data
                                                           Layer

  **Standard     99.0%         1 ساعت        1 ساعت        Dashboard،
  (Tier 3)**                                               Reporting

  **Background   95.0%         4 ساعت        12 ساعت       Backtest،
  (Tier 4)**                                               Analytics
  ----------------------------------------------------------------------

> **مرجع:** پلتفرم‌های معامله‌گری مالی معمولاً RTO زیر ۲ ساعت و RPO زیر ۱۵
> دقیقه را هدف قرار می‌دهند
> ([SentinelOne](https://www.sentinelone.com/cybersecurity-101/cloud-security/rto-vs-rpo/)‌،
> [Veeam](https://www.veeam.com/blog/recovery-time-recovery-point-objectives.html)‌).

### ۱۳.۲ SLO Error Budget

-   هر ماه، error budget = (100% - SLA target) × total_minutes
-   اگر error budget مصرف شد → freeze risky releases
-   اگر در ۲ ماه متوالی مصرف شد → architecture review

### ۱۳.۳ Incident Severity Levels

  -----------------------------------------------------------------------
  Severity          تعریف             پاسخ اولیه        کانال
  ----------------- ----------------- ----------------- -----------------
  **P0 (Critical)** سیستم از کار      فوری              Telegram +
                    افتاده یا پول از                    Email + Phone
                    دست رفته                            

  **P1 (High)**     عملکرد اصلی مختل  ۵ دقیقه           Telegram + Email

  **P2 (Medium)**   عملکرد غیرحیاتی   ۳۰ دقیقه          Telegram
                    مختل                                

  **P3 (Low)**      مشکل جزئی         2 ساعت            Dashboard
  -----------------------------------------------------------------------

### ۱۳.۴ Operational Runbooks

#### Runbook 1: قطعی داده بازار (Data Provider Outage)

1.  Stale Data Circuit Breaker خودکار فعال
2.  بررسی منبع داده
3.  تلاش fallback
4.  اگر \> ۵ دقیقه: توقف کامل
5.  notify کاربر
6.  پس از بازیابی: reconciliation

#### Runbook 2: قطعی API صرافی

1.  Exchange Circuit Breaker خودکار
2.  بررسی وضعیت صرافی
3.  تلاش اتصال مجدد هر ۵ دقیقه
4.  notify کاربر
5.  اگر \> ۳۰ دقیقه: بررسی manual close
6.  اگر پوزیشن در معرض ریسک: Kill Switch

#### Runbook 3: تخریب Redis

1.  Fallback به PostgreSQL
2.  کاهش rate limiting
3.  notify Admin
4.  بررسی maxmemory policy
5.  اگر \> ۱۰ دقیقه: توقف معاملات

#### Runbook 4: تخریب DB

1.  توقف کامل (fail-closed)
2.  بررسی read replica
3.  notify Admin (P0)
4.  اگر \> ۵ دقیقه: Kill Switch

#### Runbook 5: Drawdown غیرعادی

1.  Drawdown \> Soft (8%): کاهش خودکار به ۵۰%
2.  Drawdown \> Hard (12%): توقف معاملات جدید
3.  تحلیل root cause
4.  Drawdown \> Kill (15%): Kill Switch

#### Runbook 6: داده Stale

1.  Stale Data Breaker فعال
2.  بررسی WebSocket
3.  تلاش reconnect
4.  اگر \> ۵ دقیقه: توقف کامل

#### Runbook 7: شکست Reconciliation

1.  توقف کامل معاملات
2.  مقایسه local vs exchange state
3.  شناسایی اختلاف
4.  تصمیم: manual correction یا kill switch

### ۱۳.۵ API Key Leak Runbook (پاسخ به نقد #۱۰)

> **نقد تیم فنی:** «در صورت leak شدن API Key صرافی، سناریوی "کلید leak
> شد و سفارش مخرب ثبت شد" workflow ندارد. HSM یا Vault برای نگهداری
> کلیدها ذکر نشده.»

#### سناریو: API Key Leak + سفارش مخرب

**مرحله ۱: Detection (تشخیص)**

سیستم باید به‌صورت خودکار نشانه‌های leak را تشخیص دهد:

  نشانه                     آستانه                             اقدام          
  ------------------------- ---------------------------------- -------------- --
  سفارش از IP ناشناخته      IP ∉ whitelist                     هشدار فوری     
  حجم سفارش غیرعادی         size \> max_position_size × 2      هشدار + توقف   
  نرخ خطای امضا غیرعادی     signature_errors \> 5 در ۱ دقیقه   هشدار          
  فعالیت در ساعات غیرعادی   تراکنش در ۳-۶ صبح UTC              هشدار          
  الگوی معاملاتی غیرعادی    تفاوت با الگوی معمول کاربر         هشدار          

**مرحله ۲: Immediate Response (پاسخ فوری)**

``` python
class APIKeyLeakResponse:
    """Automated response to API key leak."""
    
    async def handle_suspected_leak(self, evidence: dict):
        # 1. Disable API key in local DB
        await self.disable_api_key(evidence['api_key_id'])
        
        # 2. Attempt to revoke at exchange (if supported)
        try:
            await self.exchange_adapter.revoke_api_key(evidence['api_key_id'])
        except Exception:
            # Log - manual revocation needed
            await self.audit_log('KEY_REVOCATION_FAILED', evidence)
        
        # 3. Cancel all open orders
        await self.cancel_all_open_orders()
        
        # 4. Activate Kill Switch
        await self.kill_switch.activate(
            reason=f"Suspected API key leak: {evidence['reason']}"
        )
        
        # 5. Notify user immediately
        await self.notify_user(
            severity='CRITICAL',
            message=f"SECURITY ALERT: Suspected API key leak detected. "
                    f"All trading halted. Action required: rotate API key."
        )
        
        # 6. Log to audit trail
        await self.audit_log('API_KEY_LEAK_DETECTED', evidence)
```

**مرحله ۳: Recovery (بازیابی)**

1.  کاربر API Key جدید در صرافی ایجاد می‌کند (با IP whitelist جدید)
2.  API Key جدید در Vault ذخیره می‌شود
3.  Reconciliation کامل: بررسی همه سفارش‌ها و پوزیشن‌ها
4.  اگر سفارش مخرب ثبت شده: گزارش به صرافی + درخواست rollback
5.  گزارش Incident کامل
6.  Two-Person Approval برای resume

#### مدیریت کلید با Vault + HSM/KMS

> **تغییر نسخه ۴.۱:** Vault به‌تنهایی کافی نیست. برای production، کلیدهای
> API صرافی باید با HSM یا cloud KMS محافظت شوند.

  -----------------------------------------------------------------------
  لایه                    روش                     توضیح
  ----------------------- ----------------------- -----------------------
  **Application**         HashiCorp Vault         Dynamic secrets،
                                                  lease-based، audit

  **Encryption**          HSM یا Cloud KMS        AWS KMS، Azure Key
                                                  Vault، یا PKCS#11 HSM

  **Storage**             Envelope encryption     کلید داده با DEK
                                                  رمزگذاری، DEK با KEK
                                                  (HSM) محافظت

  **Rotation**            خودکار هر ۹۰ روز        Vault dynamic secrets
                                                  یا manual rotation
  -----------------------------------------------------------------------

> **مرجع:** Vault Managed Keys از HSM و cloud KMS برای عملیات رمزنگاری
> پشتیبانی می‌کند ([HashiCorp Vault Managed
> Keys](https://developer.hashicorp.com/vault/docs/enterprise/managed-keys)‌،
> [Vault
> HSM](https://developer.hashicorp.com/vault/docs/enterprise/hsm)‌).

### ۱۳.۶ User Approval Timeout SLA (پاسخ به پیشنهاد ز)

> **پیشنهاد تیم فنی:** «اگر کاربر در بازه مشخص (مثلاً ۵ دقیقه) به سیگنال
> پاسخ نده، رفتار سیستم چیه؟ این timeout و default action باید صراحتاً در
> IPS کاربر تعریف بشه.»

#### تعریف:

> **اشکال P1 #۳ تیم فنی:** «تایم‌اوت ۵ دقیقه برای سیگنال‌های 4H/1D
> نامناسبه --- در این تایم‌فریم‌ها سیگنال معتبر می‌تونه ۳۰-۶۰ دقیقه هم
> معتبر بمونه. از طرف دیگه در بازار پرنوسان، قیمت ورود ممکنه در همین ۵
> دقیقه کاملاً تغییر کنه."

**تصمیم نسخه ۴.۲:** تایم‌اوت پویا (Dynamic Approval Timeout) بر اساس
تایم‌فریم سیگنال + انقضای اضافی بر اساس انحراف قیمت.

  تایم‌فریم سیگنال   `approval_timeout` پیش‌فرض   توضیح
  ----------------- --------------------------- ---------------------------------
  1H                ۵ دقیقه                     بازار پرنوسان --- انقضای سریع
  4H                ۳۰ دقیقه                    سیگنال بلندمدت‌تر --- مهلت بیشتر
  1D                ۴ ساعت                      سیگنال روزانه --- مهلت طولانی

**انقضای اضافی بر اساس انحراف قیمت:** اگر قیمت فعلی بیش از ۰.۲٪ از نقطه
ورود پیشنهادی فاصله داشته باشد، سیگنال حتی قبل از timeout نیز منقضی
می‌شود.

``` python
class ApprovalTimeoutHandler:
    """Handle user approval timeout for signals — dynamic by timeframe."""
    
    TIMEOUT_BY_TIMEFRAME = {
        '1H': timedelta(minutes=5),
        '4H': timedelta(minutes=30),
        '1D': timedelta(hours=4),
    }
    PRICE_DRIFT_THRESHOLD = 0.002  # 0.2% from suggested entry
    
    async def check_timeout(self, signal_id: str):
        signal = await self.get_signal(signal_id)
        timeout = self.TIMEOUT_BY_TIMEFRAME.get(signal.timeframe, timedelta(minutes=5))
        # IPS timeout is an optional downward-only cap; it cannot extend
        # the safety-oriented timeframe default. None preserves Dynamic Timeout.
        if self.ips.approval_timeout_minutes is not None:
            timeout = min(
                timeout,
                timedelta(minutes=self.ips.approval_timeout_minutes)
            )
        default_action = self.ips.default_action_on_timeout  # EXPIRE or REJECT
        
        elapsed = datetime.utcnow() - signal.created_at
        
        # Check 1: Time-based expiry
        if elapsed > timeout:
            await self.expire_signal(signal_id, default_action, timeout)
            return
        
        # Check 2: Price drift-based expiry (even before timeout)
        current_price = await self.get_current_price(signal.symbol)
        price_drift = abs(current_price - signal.reference_price) / signal.reference_price
        if price_drift > self.PRICE_DRIFT_THRESHOLD:
            await self.expire_signal(
                signal_id, 'PRICE_DRIFT_EXPIRED',
                f'Price drifted {price_drift:.2%} from entry'
            )
            return
    
    async def expire_signal(self, signal_id, action, reason):
        await self.update_signal_status(signal_id, action)
        await self.notify_user(f"Signal {signal_id} expired: {reason}")
        await self.audit_log('APPROVAL_TIMEOUT', signal_id=signal_id, action=action, reason=reason)
```

#### معیار پذیرش:

-   [ ] `approval_timeout_minutes` در IPS اختیاری است و فقط می‌تواند timeout پویا را کاهش دهد (۳-۲۴۰ دقیقه)
-   [ ] در صورت `None` بودن، timeout پویا بر اساس timeframe بدون override اجرا می‌شود
-   [ ] `default_action_on_timeout` در IPS تعریف شده
-   [ ] سیستم به‌صورت خودکار timeout را تشخیص می‌دهد
-   [ ] هیچ سیگنالی بدون تأیید صریح اجرا نمی‌شود
-   [ ] timeout در audit log ثبت می‌شود

### ۱۳.۷ One-Page Runbooks برای نقاط شکست (پاسخ به پیشنهاد ه)

> **پیشنهاد تیم فنی:** «برای هر یک از ۱۰ نقطه شکست، یک Runbook یک‌صفحه‌ای
> بنویس: علائم، اقدام فوری، escalation path.»

#### قالب واحد Runbook:

``` markdown
# Runbook: [نام نقطه شکست]

## علائم (Symptoms)
- [نشانه ۱]
- [نشانه ۲]

## تشخیص (Diagnosis)
1. [گام تشخیص ۱]
2. [گام تشخیص ۲]

## اقدام فوری (Immediate Action)
1. [اقدام ۱]
2. [اقدام ۲]

## Escalation Path
- [سطح ۱: Operator]
- [سطح ۲: Admin]
- [سطح ۳: Two-Person Approval]

## Resume Criteria
- [معیار ۱]
- [معیار ۲]

## Postmortem
- [گام مستندسازی]
```

#### خلاصه Runbook‌ها (مرجع کامل در بخش ۱۳.۴):

  -----------------------------------------------------------------------
  \#                نقطه شکست         اقدام فوری        Escalation
  ----------------- ----------------- ----------------- -----------------
  ۱                 داده خارجی قطع    Stale Data        Operator → Admin
                                      Breaker، fallback 

  ۲                 DB قطع            توقف کامل، read   Admin (P0)
                                      replica           

  ۳                 Redis قطع         Fallback به DB    Operator → Admin

  ۴                 Auth service قطع  Token caching،    Admin
                                      read-only         

  ۵                 Notification قطع  Queue، retry،     Operator
                                      fallback channel  

  ۶                 Risk Engine قطع   Default deny،     Admin (P0)
                                      cache limits      

  ۷                 Connector صرافی   Circuit Breaker،  Operator → Admin
                    قطع               fallback provider 

  ۸                 مدل تحلیل قطع     Input/output      Operator
                                      validation،       
                                      fallback به       
                                      rule-based        

  ۹                 Scheduler قطع     Distributed lock، Operator
                                      dead letter queue 

  ۱۰                زیرساخت قطع       Multi-AZ،         Admin (P0)
                                      auto-scaling، DNS 
                                      failover          
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## ۱۴. Data Governance و Privacy

### ۱۴.۱ طبقه‌بندی داده (Data Classification)

  ------------------------------------------------------------------------
  طبقه               نوع داده          مثال              سیاست
  ------------------ ----------------- ----------------- -----------------
  **Critical**       داده مالی حساس    API Keys، Wallet  رمزگذاری
                                       Addresses         at-rest +
                                                         in-transit، HSM

  **Confidential**   داده کاربر        نام، ایمیل، KYC   رمزگذاری، RBAC،
                                                         retention

  **Internal**       داده عملیاتی      Orders، Signals   رمزگذاری، audit،
                                                         retention ۹۰ روز

  **Public**         داده بازار        OHLCV، Ticker     retention ۳ سال
  ------------------------------------------------------------------------

### ۱۴.۲ رمزگذاری (Encryption)

  حالت                 روش               جزئیات
  -------------------- ----------------- ----------------------------------------
  **At-Rest**          AES-256-GCM       PostgreSQL + Vault envelope encryption
  **In-Transit**       TLS 1.3           تمام ارتباطات
  **Key Management**   Vault + HSM/KMS   HSM برای production keys
  **Backup**           AES-256           Backup‌های رمزگذاری‌شده

### ۱۴.۳ دوره نگهداری داده (Data Retention)

  نوع داده              دوره          پس از انقضا
  --------------------- ------------- -----------------
  OHLCV                 ۳ سال         Cold storage
  Audit Log             ۵ سال         Cold storage
  Transaction History   ۵ سال         حذف پس از تأیید
  User Profile          تا حذف حساب   Soft delete
  Signal Data           ۱ سال         حذف خودکار
  Decision Journal      ۵ سال         Cold storage

### ۱۴.۴ حقوق کاربر (User Rights)

-   **دسترسی:** مشاهده تمام داده‌های خود
-   **اصلاح:** ویرایش پروفایل
-   **حذف:** حذف حساب (soft delete + retention)
-   **صادرات:** دریافت داده در JSON/CSV
-   **Objection:** توقف پردازش داده‌های خاص

------------------------------------------------------------------------

## ۱۵. Compliance و Regulatory Risk

### ۱۵.۱ Regulatory Decision Gate

الزامات قانونی بسته به نوع سیستم متفاوت است:

  مدل کسب‌وکار                    الزامات                           سطح ریسک
  ------------------------------ --------------------------------- ------------
  **ابزار شخصی (Self-hosted)**   حداقل --- مالیات شخصی             پایین
  **پلتفرم سیگنال‌دهی**           Disclaimer، احتمالاً مجوز انتشار   متوسط
  **اجرای با API Key کاربر**     بررسی شرایط API صرافی             متوسط-بالا
  **صرافی/کاستودین**             مجوز کامل CBI، KYC/AML            بحرانی

> **تأکید:** الزامات بسته به مدل کسب‌وکار متفاوت است. پیش از production،
> مشاوره حقوقی ضروری است.

### ۱۵.۲ چارچوب قانونی ایران (۲۰۲۵)

بانک مرکزی ایران (CBI) در دسامبر ۲۰۲۴ «چارچوب سیاستی و مقرراتی رمزارزها»
را تصویب کرد ([Tehran
Times](https://www.tehrantimes.com/news/507174/Central-bank-approves-regulatory-framework-for-cryptocurrencies)‌،
[Crystal
Intelligence](https://crystalintelligence.com/investigations/beyond-the-headlines-of-irans-crypto-usage/)‌،
[Financial Tribune](https://financialtribune.com/node/119424)‌).

### ۱۵.۳ ریسک‌های قانونی

  ریسک                 احتمال   تأثیر    استراتژی
  -------------------- -------- -------- -------------------------------
  تغییر قوانین ایران   بالا     بحرانی   طراحی ماژولار، مشاوره حقوقی
  تحریم‌ها              متوسط    بحرانی   عدم استفاده از خدمات تحریم‌شده
  AML/CFT              متوسط    بالا     KYC، transaction monitoring

### ۱۵.۴ محدودیت‌های صرافی‌های داخلی (پاسخ به نقد #۴)

> **نقد تیم فنی:** «محدودیت‌های خاص صرافی‌های داخلی (والکس، نوبیتکس) در
> مقایسه با بین‌المللی مستند نشده.»

#### مقایسه والکس و نوبیتکس (بر اساس مستندات رسمی):

  -----------------------------------------------------------------------
  ویژگی             Wallex            Nobitex           Binance
                                                        (بین‌المللی)
  ----------------- ----------------- ----------------- -----------------
  **احراز هویت      API Key +         API Key +         API Key + Secret
  API**             Signature (طبق    Ed25519 +         (HMAC)
                    منبع third-party  Timestamp         
                    --- نیازمند تأیید (تأییدشده)        
                    رسمی)                               

  **محدودیت IP**    پشتیبانی از IP    پشتیبانی از IP    IP Restriction
                    Whitelist         Whitelist         
                    (تأییدشده)        (تأییدشده)        

  **دسترسی          باید به‌صورت       دسترسی `WITHDRAW` باید فعال شود
  Withdrawal**      جداگانه فعال شود  جداگانه           

  **Emergency       در مستند رسمی     پشتیبانی          API + UI
  Cancel**          مشاهده نشد        (تأییدشده)        
                    (نیازمند تأیید)                     

  **Rate Limit**    طبق منبع          متغیر per         ۶۰۰۰ وزن/دقیقه/IP
                    third-party: ۵    endpoint          
                    req/s، ۴۳۲k/day                     
                    (نیازمند تأیید                      
                    رسمی)                               

  **Timestamp       در مستند رسمی     حداکثر ۳۰ ثانیه   \_recvWindow
  Validation**      مشاهده نشد        اختلاف با سرور    
                    (نیازمند تأیید)   (تأییدشده)        

  **IP              فقط IP‌های مجاز در فقط IP‌های ایران   بدون محدودیت
  Restrictions**    فهرست (تأییدشده)  (تأییدشده)        جغرافیایی

  **نوع معامله**    Spot              Spot + Margin +   Spot + Futures +
                                      Perpetual         Options

  **حذف Withdrawal  توصیه: فقط READ + توصیه: فقط        توصیه: بدون
  از API Key**      TRADE             `READ,TRADE`      WITHDRAW
  -----------------------------------------------------------------------

> **منابع:** [Wallex API
> Documentation](https://developers.wallex.ir/docs/)‌، [Nobitex API Key
> Guide](https://apidocs.nobitex.ir/api_key/api-key-guide)‌، [Nobitex
> Security](https://apidocs.nobitex.ir/security/api-%D8%A7%D9%85%D9%86%DB%8C%D8%AA-%D9%86%D9%88%D8%A8%DB%8C%D8%AA%DA%A9%D8%B3)‌،
> [SingaporeAPI Wallex](https://singaporeapi.com/apis/wallex)‌)

#### توصیه‌های امنیتی برای صرافی‌های داخلی:

1.  **API Key با حداقل دسترسی:** فقط `READ` + `TRADE` --- هرگز
    `WITHDRAW` فعال نشود
2.  **IP Whitelist:** فقط IP سرور ربات در فهرست مجاز قرار گیرد
3.  **Timestamp Validation:** اطمینان از sync سرور NTP (بویژه نوبیتکس با
    ۳۰ ثانیه اختلاف مجاز)
4.  **Emergency Cancel:** در صورت دسترسی، فعال‌سازی emergency cancel برای
    نوبیتکس
5.  **Separate Keys:** برای Paper و Live محیط، API Key‌های مجزا
6.  **Key Rotation:** هر ۹۰ روز در Vault

#### تطبیق با تغییرات مقرراتی:

1.  **مانیتورینگ تغییرات:** بررسی دوره‌ای وضعیت مقررات CBI
2.  **طراحی ماژولار:** قابلیت تطبیق سریع با تغییرات
3.  **Separation of AML:** AML داخلی (Iran-specific) از international
    AML تفکیک شده --- سیاست‌های جداگانه
4.  **نیازمند بررسی حقوقی/فنی صرافی قبل از production**

### ۱۵.۵ Compliance Checklist

-   [ ] مشاوره حقوقی قبل از production
-   [ ] KYC/AML برای کاربران
-   [ ] Sanctioned address screening
-   [ ] Disclaimer در تمام خروجی‌ها
-   [ ] کاربر ریسک‌ها را تأیید کرده
-   [ ] Audit trail کامل
-   [ ] Data retention policy اجرا می‌شود
-   [ ] Incident reporting procedure تعریف شده

------------------------------------------------------------------------

## ۱۶. استراتژی Multi-tenancy

### ۱۶.۱ تصمیم نهایی: Multi-Tenant با Row-Level Security (Post-MVP)

> **تغییر نسخه ۴.۱:** RLS از MVP-0 حذف شد. MVP-0 single-tenant است. RLS
> فقط در Post-MVP با Benchmark Gate فعال می‌شود.

#### فازبندی:

  -----------------------------------------------------------------------
  فاز                     حالت                    توضیح
  ----------------------- ----------------------- -----------------------
  **MVP-0**               Single-tenant           یک کاربر، بدون RLS،
                                                  بدون tenant_id

  **Post-MVP**            Multi-tenant با RLS     با Benchmark Gate و
                                                  performance validation
  -----------------------------------------------------------------------

### ۱۶.۲ Benchmark Gate برای RLS (پاسخ به نقد #۹)

> **نقد تیم فنی:** «RLS در PostgreSQL برای تعداد کاربر بالا می‌تواند
> bottleneck بشه. هیچ‌جا benchmark یا حداکثر تعداد کاربر هم‌زمان ذکر
> نشده.»

#### معیارهای Benchmark:

  -----------------------------------------------------------------------
  معیار                   آستانه هدف              توضیح
  ----------------------- ----------------------- -----------------------
  **p95 Query Latency**   \< 50ms                 برای query‌های متداول
                                                  (signals، orders)

  **p99 Query Latency**   \< 100ms                برای query‌های متداول

  **Overhead vs no-RLS**  \< 15%                  RLS نباید بیش از ۱۵٪
                                                  overhead اضافه کند

  **Max Concurrent        1000                    با p95 \< 50ms
  Tenants**                                       

  **Max Concurrent        100                     همزمان فعال
  Users**                                         
  -----------------------------------------------------------------------

#### Threshold‌های عملکرد:

-   اگر RLS overhead \> ۱۵٪: بررسی Index optimization
-   اگر p95 \> 50ms: بررسی Query Plan و Index
-   اگر p95 \> 100ms با Index: fallback به schema-per-tenant برای جداول
    حساس
-   اگر p95 \> 200ms: app-level tenant isolation (tenant_id در WHERE
    clause)

#### مرجع:

> RLS در PostgreSQL policy را برای هر row ارزیابی می‌کند. بدون Index
> مناسب، overhead می‌تواند ۵-۱۵٪ برای query‌های ساده و بیشتر برای query‌های
> پیچیده باشد
> ([dev.to](https://dev.to/canu/why-we-stopped-using-row-level-security-after-1m-rows-4dpb)‌،
> [Supabase](https://supabase.com/docs/guides/database/postgres/row-level-security-performance)‌،
> [PlanetScale](https://planetscale.com/blog/rls-sounds-great-until-it-isnt)‌).

#### استراتژی Fallback:

``` python
class TenantIsolationStrategy:
    """Progressive tenant isolation strategy."""
    
    def get_strategy(self, tenant_count: int, p95_latency: float) -> str:
        if tenant_count < 100:
            return "shared_tables_rls"  # RLS on all tables
        elif p95_latency < 50:
            return "shared_tables_rls"  # RLS still OK
        elif p95_latency < 100:
            return "rls_sensitive_only"  # RLS only on sensitive tables
        else:
            return "schema_per_tenant"  # Separate schema per tenant
```

------------------------------------------------------------------------

## ۱۷. مدل‌های ML: Shadow Mode، Promotion و A/B Testing

### ۱۷.۱ چرخه حیات مدل

    Development → Shadow Mode → Canary → A/B Testing → Production → Monitoring → Retirement

### ۱۷.۲ Shadow Mode و Promotion Criteria

#### معیارهای Promotion:

  معیار                  آستانه              توضیح
  ---------------------- ------------------- -----------------------------
  Agreement Rate         ≥ ۸۰٪               تطابق با مدل production
  Sharpe Ratio           ≥ ۱.۲× production   در داده shadow
  Max Drawdown           ≤ ۹۰٪ production    DD کمتر یا مساوی
  Latency p99            ≤ ۱.۵× production   تاخیر قابل قبول
  Error Rate             \< ۱٪               نرخ خطای runtime
  Distribution Drift     \< ۰.۱ (KS test)    توزیع خروجی شبیه production
  **Minimum Duration**   **۶ هفته**          حداقل مدت shadow

### ۱۷.۳ Baseline Model (پاسخ به نقد #۵)

> **نقد تیم فنی:** «Baseline model چیه؟ اگر مدل ML شکست بخورد، سیستم به
> چی برمی‌گرده؟»

#### تعریف Baseline Model:

سیستم در صورت شکست مدل ML به یک **rule-based deterministic model**
برمی‌گردد. این baseline هیچ وابستگی به ML ندارد و با قواعد قطعی کار
می‌کند.

  -----------------------------------------------------------------------
  ویژگی                   Baseline Model          ML Model
  ----------------------- ----------------------- -----------------------
  **نوع**                 Rule-based              Statistical/ML
                          deterministic           

  **سیگنال ورود**         Trend Following (EMA +  Multi-factor ML
                          Volume)                 

  **Position Sizing**     Fixed Fractional (0.5%) Kelly-capped +
                                                  Volatility targeting

  **Stop Loss**           ATR-based (2× ATR)      Dynamic (regime-aware)

  **وابستگی به داده       بدون                    نیاز به بک‌تست
  آموزش**                                         

  **قابلیت توضیح**        بالا (شفاف)             متوسط

  **عملکرد مورد انتظار**  Sharpe ≥ ۰.۵ (OOS)      Sharpe ≥ ۱.۰ (OOS)
  -----------------------------------------------------------------------

#### Fallback Logic:

``` python
class ModelFallbackManager:
    """Manages fallback from ML model to baseline."""
    
    def get_active_model(self):
        if self.ml_model.is_healthy():
            return self.ml_model
        else:
            # Fallback to baseline rule-based model
            return self.baseline_model
    
    def check_ml_health(self) -> bool:
        """Check if ML model is healthy enough to use."""
        if self.ml_model.drift > self.drift_threshold:
            return False
        if self.ml_model.error_rate > 0.05:  # > 5% errors
            return False
        if self.ml_model.latency_p99 > self.latency_threshold:
            return False
        return True
```

#### شرط فعال‌سازی ML:

ML فقط زمانی فعال می‌شود که: 1. حداقل ۱۰۰ معامله در بک‌تست ثبت شده باشد 2.
Sharpe Ratio OOS ≥ ۰.۵ باشد 3. Baseline model حداقل ۳ ماه در production
پایدار بوده باشد 4. ML در Shadow Mode حداقل ۶ هفته تست شده باشد 5. تمام
معیارهای Promotion برآورده شده باشد

#### شرط غیرفعال‌سازی (Rollback به Baseline):

-   drift \> threshold (PSI \> 0.2 یا K-S test p \< 0.05)
-   error_rate \> ۵٪
-   Sharpe \< ۸۰٪ production (baseline)
-   Distribution drift \> ۰.۲ (KS test)

### ۱۷.۴ Rollback Criteria

-   Sharpe مدل \< baseline
-   Max Drawdown \> ۱.۲× baseline
-   Error rate \> ۵٪
-   → Rollback فوری به baseline

### ۱۷.۵ A/B Testing Framework

``` python
class ABTestFramework:
    def __init__(self, model_a, model_b, traffic_split=0.5):
        self.model_a = model_a  # Control (baseline)
        self.model_b = model_b  # Variant (ML)
        self.traffic_split = traffic_split
    
    async def route_and_predict(self, input_data, user_id):
        bucket = 'b' if hash(user_id) % 100 < self.traffic_split * 100 else 'a'
        prediction = await (self.model_b if bucket == 'b' else self.model_a).predict(input_data)
        return prediction
```

**Guardrails:** - حداکثر ۱۰٪ کاربران در variant - حداقل ۱۰۰ معامله در هر
bucket قبل از ارزیابی - Risk limits یکسان برای هر دو bucket

------------------------------------------------------------------------

## ۱۸. Stress Testing Module

### ۱۸.۱ سناریوهای تست فشار

  سناریو                  توضیح                 پارامتر
  ----------------------- --------------------- -------------------------
  Flash Crash             ریزش ۳۰٪ در ۴۸ ساعت   BTC -30٪، Altcoins -50٪
  Extended Bear           ریزش ۶۰٪ در ۳ ماه     BTC -60٪، Altcoins -75٪
  Volatility Spike        ATR ۳× میانگین        نوسان ۳ برابر
  Correlation Breakdown   همبستگی → ۱.۰         ریزش همزمان
  Liquidity Crisis        حجم ۸۰٪ کاهش          spread گسترده
  Exchange Failure        صرافی اصلی قطع        عدم close
  Black Swan              ترکیبی                ریزش + نقدشوندگی پایین

### ۱۸.۲ Monte Carlo Simulation

``` python
class MonteCarloStressTest:
    def __init__(self, portfolio, n_simulations=10000, time_horizon_days=90):
        self.portfolio = portfolio
        self.n_simulations = n_simulations
        self.time_horizon = time_horizon_days
    
    def run_simulation(self):
        # Generate correlated random returns
        # Apply to portfolio
        # Analyze results: VaR, Max DD, Probability of Ruin
        pass
```

### ۱۸.۳ معیارهای پذیرش

  معیار                            آستانه
  -------------------------------- -----------
  Max Drawdown (95th percentile)   \< ۱۵٪
  Probability of Ruin              \< ۱٪
  VaR 95% (90-day)                 \< ۱۰٪
  Recovery Time                    \< ۶۰ روز

> **مرجع:** Monte Carlo simulation با هزاران مسیر تصادفی، توزیع کامل
> نتایج ممکن را تولید می‌کند
> ([arXiv](https://ar5iv.labs.arxiv.org/html/2507.08915)‌،
> [VolatiCloud](https://docs.volaticloud.com/docs/simulations/overview)‌).

------------------------------------------------------------------------

## ۱۹. Mobile-first UI و UX

### ۱۹.۱ PWA (Progressive Web App)

-   **Frontend:** Vue.js 3 یا React 18
-   **پوشش:** PWA با Responsive Design (Mobile-first)

#### معیارهای UX:

  معیار                    آستانه
  ------------------------ --------------
  First Contentful Paint   \< ۱.۵ ثانیه
  Time to Interactive      \< ۳ ثانیه
  Lighthouse Score         ≥ ۹۰

### ۱۹.۲ استراتژی آفلاین (پاسخ به نقد #۸)

> **نقد تیم فنی:** «PWA پیشنهاد شده ولی در بازار رمزارز ایران با اینترنت
> ناپایدار، استراتژی آفلاین مشخص نیست --- آیا تأییدیه معامله در حالت
> آفلاین ممکنه یا قفل می‌شه؟»

#### قانون اصلی: تأیید معامله در حالت آفلاین ممنوع است.

  -----------------------------------------------------------------------
  قابلیت            Online            Offline           توضیح
  ----------------- ----------------- ----------------- -----------------
  **مشاهده          ✅ کامل           ✅ کش‌شده          داده آخرین بار
  داشبورد**                           (read-only)       معتبر

  **مشاهده          ✅ زنده           ✅ کش‌شده          ممکن است stale
  پوزیشن‌ها**                                            باشد

  **دریافت سیگنال** ✅                ❌                نیاز به داده زنده

  **تأیید سیگنال**  ✅                ❌ ممنوع          تأیید آفلاین
                                                        ریسکناک است

  **ثبت سفارش**     ✅                ❌ ممنوع          نیاز به داده زنده
                                                        و Risk Engine

  **Kill Switch**   ✅                ✅ (local)        همیشه قابل
                                                        فعال‌سازی

  **نوتیفیکیشن**    ✅                ✅ (queued)       پس از reconnect
                                                        ارسال
  -----------------------------------------------------------------------

#### Service Worker Strategy:

``` javascript
// service-worker.js

// Cache-first for static assets (App Shell)
const CACHE_STRATEGY = {
  static: 'cache-first',
  api_market_data: 'network-first', // Try network, fall back to cache
  api_trade: 'network-only',         // Never cache trade-related
  api_auth: 'network-only',          // Never cache auth
};

// Offline page for trade-related actions
self.addEventListener('fetch', (event) => {
  if (event.request.url.includes('/api/trade') || 
      event.request.url.includes('/api/approval')) {
    // Network-only — no offline fallback
    event.respondWith(fetch(event.request));
    return;
  }
  
  if (event.request.url.includes('/api/dashboard')) {
    // Network-first with cache fallback for read-only data
    event.respondWith(
      fetch(event.request)
        .catch(() => caches.match(event.request))
    );
    return;
  }
});
```

#### رفتار سیستم در قطع اینترنت:

1.  **کاربر سیگنال دریافت می‌کند** → نوتیفیکیشن در صف (queued)
2.  **اگر اینترنت قطع است:**
    -   سیگنال `PENDING_APPROVAL` باقی می‌ماند
    -   تایمر انقضا ادامه می‌یابد
    -   اگر کاربر قبل از timeout اینترنت برگردد: می‌تواند تأیید کند
    -   اگر timeout شود: سیگنال `EXPIRED` می‌شود (پاسخ به پیشنهاد ز)
3.  **اگر کاربر در حال تأیید است و اینترنت قطع می‌شود:**
    -   درخواست تأیید ثبت نمی‌شود
    -   کاربر پیام «اتصال برقرار نیست --- تأیید ممکن نیست» دریافت می‌کند
    -   سیگنال در وضعیت `PENDING_APPROVAL` باقی می‌ماند تا timeout

> **مرجع:** PWA best practices توصیه می‌کنند static assets با cache-first
> و dynamic content با network-first یا stale-while-revalidate کش شوند.
> Auth و trade endpoints باید network-only باشند
> ([MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Best_practices)‌،
> [web.dev](https://web.dev/learn/pwa/service-workers)‌،
> [Metasphere](https://msphere.io/insights/progressive-web-apps-offline/)‌).

------------------------------------------------------------------------

## ۲۰. Exit Strategy برای وابستگی‌های خارجی

### ۲۰.۱ Adapter Pattern با Provider Scoring

``` python
class ExchangeAdapterRegistry:
    def register(self, name: str, adapter: ExchangeAdapter):
        self.adapters[name] = adapter
        self.scores[name] = 1.0
    
    def get_best(self) -> ExchangeAdapter:
        best = max(self.scores, key=self.scores.get)
        return self.adapters[best]
    
    def update_score(self, name: str, score: float):
        self.scores[name] = score
        if score < 0.5:
            self._alert_degraded(name, score)
```

### ۲۰.۲ Provider Scoring

  معیار                 وزن
  --------------------- -----
  API Uptime (۳۰ روز)   ۳۰٪
  Latency p99           ۲۰٪
  Error Rate            ۲۰٪
  Data Quality          ۱۵٪
  Rate Limit Headroom   ۱۵٪

### ۲۰.۳ Provider Replacement Playbook

1.  Detection: Provider score \< 0.5 برای ۲۴ ساعت
2.  Investigation: بررسی علت
3.  If permanent: فعال‌سازی adapter پشتیبان
4.  Migration: انتقال تدریجی
5.  Decommission: حذف provider قدیمی

### ۲۰.۴ اصل "No Provider-Specific Logic in Domain Layer"

-   تمام منطق کسب‌وکار provider-agnostic
-   Provider-specific logic فقط در adapter layer
-   Contract tests برای هر adapter

------------------------------------------------------------------------

## ۲۱. ایده‌های تکمیلی برای ارتقای طرح

### ۲۱.۱ مدل توصیه با بودجه عدم‌قطعیت

``` python
@dataclass
class UncertaintyAwareRecommendation:
    recommendation: str
    confidence: float
    uncertainty_budget: float
    adjusted_size: float
```

### ۲۱.۲ Decision Journal با Feedback Loop

``` python
class DecisionJournal:
    def record_decision(self, signal_id, user_action, reason, prediction):
        self.db.insert('decision_journal', {...})
    
    def evaluate_predictions(self, days=30):
        # Compare predictions with actual outcomes
        # Generate accuracy report
        pass
```

**Feedback Loop:** - پس از ۳۰ روز: گزارش اولیه - پس از ۹۰ روز: گزارش
کامل - اگر دقت \< ۶۰٪ → هشدار برای Retrain

### ۲۱.۳ Digital Twin / Replay

-   بازپخش رخدادهای گذشته برای بازتولید علت
-   امکان debug با داده تاریخی

### ۲۱.۴ Model and Data Governance

``` python
@dataclass
class ModelGovernance:
    model_id: str
    version: str
    owner: str
    drift_threshold: float
    rollback_rule: str
    status: str  # development, shadow, canary, production, retired
```

### ۲۱.۵ Decision Log با Visual Audit UI (پاسخ به پیشنهاد ب)

> **پیشنهاد تیم فنی:** «علاوه بر decision_journal، یک رابط کاربری ساده
> برای نمایش "چرا این سیگنال داده شد" پیش‌بینی کن.»

#### رابط کاربری Visual Audit:

``` python
class SignalExplanationUI:
    """UI component for explaining why a signal was generated."""
    
    def render_explanation(self, signal_id: str) -> dict:
        signal = self.get_signal(signal_id)
        
        return {
            'signal_id': signal.id,
            'symbol': signal.symbol,
            'direction': signal.direction,
            'timestamp': signal.timestamp,
            
            'entry_reason': signal.explanation['entry_reason'],
            # e.g., "EMA50 > EMA200 (4h uptrend) + breakout above 20-bar 
            #        high with 1.8x volume"
            
            'risk_reason': signal.explanation['risk_reason'],
            # e.g., "Stop at 2x ATR (61800), R/R = 2.1, risk = 0.5% equity"
            
            'confluence_score': signal.explanation['confluence_score'],
            # e.g., 3 (out of 5 possible confirmations)
            
            'regime': signal.explanation['regime'],
            # e.g., "trending_up"
            
            'factors': [
                {'name': 'Trend Filter', 'value': 'Bullish', 'weight': 0.30},
                {'name': 'Volume', 'value': '1.8x avg', 'weight': 0.15},
                {'name': 'ATR', 'value': '2.0x', 'weight': 0.25},
            ],
            
            'risk_metrics': {
                'position_size': signal.suggested_position_size,
                'stop_loss': signal.stop_loss_price,
                'take_profit': signal.take_profit_price,
                'risk_reward': signal.risk_reward_ratio,
            },
            
            'user_decision': self.get_user_decision(signal_id),
            # e.g., "Approved at 14:05 UTC — reason: agreed with trend confirmation"
        }
```

#### صفحه نمایش:

1.  **نمودار قیمت با نشانگر ورود/خروج** --- نقاط ورود، SL، TP روی نمودار
2.  **جدول عوامل تأثیرگذار** --- هر عامل با وزن و مقدار
3.  **متن توضیح به زبان ساده** --- «چرا این سیگنال تولید شد»
4.  **تصمیم کاربر** --- چه تصمیمی گرفته و چرا
5.  **نتیجه (در صورت بسته شدن)** --- آیا سیگنال سودآور بود

> **هدف:** کاربر بتواند با نگاه به یک صفحه، تمام منطق پشت یک سیگنال را
> درک کند. این هم به اعتماد کاربر کمک می‌کند و هم برای debug مدل‌ها حیاتی
> است.

------------------------------------------------------------------------

## ۲۲. تحلیل نقاط شکست معماری و ماتریس ریسک

### ۲۲.۱ نقاط شکست معماری

  -------------------------------------------------------------------------
  \#            نقطه شکست      احتمال        تأثیر         راهکار
  ------------- -------------- ------------- ------------- ----------------
  ۱             وابستگی به     بالا          بالا          Multi-source
                داده خارجی                                 fallback،
                                                           circuit breaker

  ۲             وابستگی به DB  متوسط         بحرانی        Read replica،
                                                           health check

  ۳             وابستگی به     متوسط         متوسط         Fallback به DB،
                Redis                                      maxmemory policy

  ۴             وابستگی به     پایین         بالا          Token caching،
                auth                                       read-only
                                                           fallback

  ۵             وابستگی به     متوسط         پایین         Queue، retry،
                notification                               channel fallback

  ۶             وابستگی به     پایین         بحرانی        Default deny،
                Risk Engine                                cache limits

  ۷             وابستگی به     متوسط         بالا          Key rotation،
                connector                                  rate limit،
                صرافی                                      reconciliation

  ۸             وابستگی به مدل متوسط         متوسط         Input/output
                تحلیل                                      validation،
                                                           fallback به
                                                           baseline

  ۹             وابستگی به     پایین         متوسط         Distributed
                scheduler                                  lock، dead
                                                           letter queue

  ۱۰            وابستگی به     پایین         بحرانی        Multi-AZ،
                زیرساخت                                    auto-scaling،
                                                           DNS failover
  -------------------------------------------------------------------------

### ۲۲.۲ ماتریس ریسک

  -------------------------------------------------------------------------
  ریسک             احتمال      تأثیر       استراتژی         اولویت
  ---------------- ----------- ----------- ---------------- ---------------
  ریزش بازار شدید  متوسط       بحرانی      Kill Switch،     P0
                                           Stress Testing   

  قطعی API صرافی   متوسط       بالا        Circuit Breaker، P0
                                           Fallback         

  تغییر قوانین     بالا        بحرانی      طراحی ماژولار،   P0
  ایران                                    مشاوره حقوقی     

  Data Leakage     متوسط       بالا        Walk-forward،    P1
                                           Look-ahead       
                                           prevention       

  Overfitting      متوسط       متوسط       OOS testing،     P1
                                           regularization   

  API Key Leak     پایین       بحرانی      Vault+HSM، IP    P0
                                           allowlist، Leak  
                                           Runbook          

  Failed           پایین       بالا        Stop trading،    P1
  Reconciliation                           manual review    

  Model Drift      متوسط       متوسط       Monitoring،      P2
                                           rollback به      
                                           baseline         
  -------------------------------------------------------------------------

------------------------------------------------------------------------

## ۲۳. ارزیابی JEV و Baseline Metrics

### ۲۳.۱ JEV چیست؟

JEV یک مدل System One برای تصمیم‌گیری سریع و ساختاریافته است.

### ۲۳.۲ موضع نهایی (اصلاح نسخه ۴.۱)

> **پاسخ به نقد #۲:** «JEV هم در نسخه ۱ و هم نسخه ۴ با دودلی مطرح شده.
> باید یا از طرح حذف بشه یا با معیار مشخص وارد نقشه‌راه بشه.»

**تصمیم نهایی (نسخه ۴.۱):** JEV از MVP-0 حذف شد. به‌جای آن، **Baseline
Metrics** ساده‌تر تعریف شد. JEV فقط در Post-MVP و پس از پاس کردن Baseline
Metrics وارد roadmap می‌شود.

  -----------------------------------------------------------------------
  فاز                     وضعیت JEV               توضیح
  ----------------------- ----------------------- -----------------------
  **MVP-0**               حذف شده                 هیچ JEV --- فقط قواعد
                                                  قطعی و Baseline Metrics

  **Post-MVP (F1)**       Research-only           ارزیابی در محیط
                                                  تحقیقاتی، بدون تأثیر
                                                  روی production

  **Post-MVP (F2)**       Shadow Mode             در لایه‌های غیرحیاتی
                                                  (Data Quality، Audit
                                                  Triage)

  **Post-MVP (F3)**       فعال‌سازی محدود          با confidence ≥ 0.9، در
                                                  لایه‌های غیرحیاتی

  **هرگز**                ---                     در تصمیم‌های حیاتی
  -----------------------------------------------------------------------

### ۲۳.۳ الگوی پیشنهادی JEV (Post-MVP)

JEV در لایه قضاوت با confidence threshold ≥ 0.9 و به‌صورت shadow mode
اجرا می‌شود.

### ۲۳.۴ نقاط قابل استفاده (Post-MVP)

  کاربرد                    توضیح                                 Confidence Threshold
  ------------------------- ------------------------------------- ----------------------
  Data Quality Check        تشخیص stale data، anomaly detection   ≥ 0.9
  Asset Scoring Auxiliary   امتیازدهی عوامل کیفی                  ≥ 0.9
  Audit Triage              طبقه‌بندی رویدادهای audit              ≥ 0.9
  Proposal Explainability   تولید دلیل موافق/مخالف                ≥ 0.9

### ۲۳.۵ Baseline Metrics (جایگزین JEV در MVP)

> **پاسخ به پیشنهاد ج:** «اگر JEV می‌مونه، اون رو با یک متریک ساده‌تر شروع
> کن: نسبت سیگنال‌های سودده به کل سیگنال‌ها در rolling window.»

به‌جای JEV، در MVP-0 از متریک‌های ساده و قابل محاسبه با قواعد قطعی استفاده
می‌شود:

  ----------------------------------------------------------------------------------------------------
  متریک            فرمول                                                            بازه      آستانه
                                                                                    ارزیابی   هشدار
  ---------------- ---------------------------------------------------------------- --------- --------
  **Rolling Win    (W = `\frac{\text{winning trades}}{\text{total trades}}`{=tex}   ۳۰ روز    \< ۵۰٪
  Rate**           `\times 100`{=tex})                                              rolling   

  **Expectancy**   (E = (W `\times`{=tex}`\bar`{=tex}{W}) - (L                      ۳۰ روز    \< ۰
                   `\times`{=tex}`\bar`{=tex}{L}))                                  rolling   

  **Signal         (`\frac{\text{correct direction}}{\text{total signals}}`{=tex}   ۷ روز     \< ۵۵٪
  Precision@k**    `\times 100`{=tex})                                              rolling   

  **Drawdown       (`\frac{\text{asset DD}}{\text{portfolio DD}}`{=tex})            ۹۰ روز    \> ۴۰٪
  Contribution**                                                                    rolling   

  **Approval       (`\frac{\text{approved signals}}{\text{total signals}}`{=tex}    ۷ روز     \< ۲۰٪
  Rate**           `\times 100`{=tex})                                              rolling   یا \>
                                                                                              ۸۰٪

  **Average        (`\frac{\sum |\text{fill} - \text{intended}|}{n}`{=tex})         ۳۰ روز    \> ۰.۳٪
  Slippage**                                                                        rolling   
  ----------------------------------------------------------------------------------------------------

``` python
class BaselineMetrics:
    """Simple, deterministic metrics as JEV replacement for MVP."""
    
    def compute_rolling_win_rate(self, days=30) -> float:
        """Win rate over rolling N days."""
        trades = self.get_closed_trades(days=days)
        if not trades:
            return 0.0
        wins = [t for t in trades if t.pnl > 0]
        return len(wins) / len(trades) * 100
    
    def compute_expectancy(self, days=30) -> float:
        """Expectancy per trade over rolling N days."""
        trades = self.get_closed_trades(days=days)
        if not trades:
            return 0.0
        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [t.pnl for t in trades if t.pnl < 0]
        win_rate = len(wins) / len(trades) if trades else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0
        return (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    
    def check_alerts(self):
        """Check if any baseline metric crossed alert threshold."""
        alerts = []
        if self.compute_rolling_win_rate() < 50:
            alerts.append("Win rate below 50% in last 30 days")
        if self.compute_expectancy() < 0:
            alerts.append("Expectancy negative in last 30 days")
        if self.compute_approval_rate() < 20:
            alerts.append("Approval rate below 20% — signals may be low quality")
        if self.compute_approval_rate() > 80:
            alerts.append("Approval rate above 80% — user may be auto-approving")
        return alerts
```

> **توضیح:** این متریک‌ها با قواعد قطعی محاسبه می‌شوند --- هیچ ML یا مدل
> آماری دخالت ندارد. هدف آن‌ها ارائه baseline ساده برای ارزیابی کیفیت
> سیگنال‌هاست. اگر این متریک‌ها در MVP پایدار شدند و ارزش خود را ثابت
> کردند، می‌توان JEV را در Post-MVP به‌صورت shadow اضافه کرد.

------------------------------------------------------------------------

## ۲۴. KPI‌های بلندمدت (۶-۱۲ ماه)

### ۲۴.۱ KPI‌های محصول (۶ ماه)

  -------------------------------------------------------------------------------
  KPI            هدف            فرمول
  -------------- -------------- -------------------------------------------------
  Sharpe Ratio   ≥ ۱.۰          ((`\mu`{=tex}- r_f) /
  (live)                        `\sigma`{=tex}`\times`{=tex}`\sqrt{365}`{=tex})

  Sortino Ratio  ≥ ۱.۵          ((`\mu`{=tex}- r_f) / `\sigma`{=tex}\_{downside}
                                `\times`{=tex}`\sqrt{365}`{=tex})

  Max Drawdown   ≤ ۱۲٪          (`\max`{=tex}((P\_{peak} - P_t) / P\_{peak}))

  Win Rate       ≥ ۵۰٪          (`\text{wins}`{=tex} / `\text{total}`{=tex}
                                `\times 100`{=tex})

  User Approval  ۳۰٪ - ۷۰٪      (`\text{approved}`{=tex} /
  Rate                          `\text{total signals}`{=tex})

  Signal Hit     ≥ ۵۵٪          (`\text{correct direction}`{=tex} /
  Rate                          `\text{total}`{=tex})

  Expectancy per \> ۰           ((W `\times`{=tex}`\bar`{=tex}{W}) - (L
  Trade                         `\times`{=tex}`\bar`{=tex}{L}))

  Total Fees as  \< ۱۵٪         (`\text{fees}`{=tex} / `\text{gross PnL}`{=tex})
  % of PnL                      

  Uptime         ≥ ۹۹.۵٪        (`\text{uptime}`{=tex} / `\text{total}`{=tex})

  Data Freshness ≤ ۵ ثانیه      میانگین تاخیر
  -------------------------------------------------------------------------------

### ۲۴.۲ KPI‌های مدل و ریسک (۶ ماه)

  KPI                          هدف
  ---------------------------- -------------
  Model Drift Rate             \< ۵٪
  Shadow Model Agreement       ≥ ۸۰٪
  Reconciliation Success       ۱۰۰٪
  Circuit Breaker Activation   \< ۲ در ماه
  Kill Switch Activation       ۰
  Audit Trail Completeness     ۱۰۰٪

### ۲۴.۳ KPI‌های کاربر و اعتماد (۱۲ ماه)

  KPI                               هدف
  --------------------------------- -------------
  Active Users (MAU)                رشد ۲۰٪/ماه
  User Retention (۹۰ روز)           ≥ ۷۰٪
  Proposal Explanation Usefulness   ≥ ۴/۵
  Incident Rate                     \< ۱ در ماه
  Decision Journal Accuracy         ≥ ۶۰٪
  Recovery Time (avg)               \< ۵ دقیقه

### ۲۴.۴ گزارش‌دهی KPI

-   **روزانه:** PnL، positions، risk metrics
-   **هفتگی:** Sharpe، win rate، signal count
-   **ماهانه:** تمام KPI‌های ۶ ماه
-   **فصلی:** KPI‌های ۱۲ ماه، استراتژی review

------------------------------------------------------------------------

## ۲۵. چک‌لیست نهایی پیش از کدنویسی

### ۲۵.۱ چک‌لیست معماری و زیرساخت

-   [ ] تصمیم نهایی Stack: Python-only برای MVP-0 (Go حذف شد)
-   [ ] ساختار Monorepo ایجاد شده
-   [ ] Docker Compose با دو network مجزا (paper + live)
-   [ ] CI/CD Pipeline ساده آماده است
-   [ ] PostgreSQL 16 نصب و migrationها موفق شده‌اند
-   [ ] Redis 7 نصب و health check آن موفق شده است
-   [ ] TimescaleDB و Vault در MVP-0 نصب/فعال نشده‌اند (Post-MVP)

### ۲۵.۲ چک‌لیست طراحی

-   [ ] API contract‌ها مستند شده‌اند
-   [ ] مدل داده حداقلی تعریف شده
-   [ ] Migration‌ها نوشته شده‌اند
-   [ ] Adapter Pattern interface تعریف شده
-   [ ] Contract tests آماده است

### ۲۵.۳ چک‌لیست ریسک و امنیت

-   [ ] نقاط شکست شناسایی و راهکار دارند
-   [ ] ماتریس ریسک تکمیل شده
-   [ ] JEV از MVP حذف شده، Baseline Metrics جایگزین شده
-   [ ] Threat model انجام شده
-   [ ] RBAC تعریف شده
-   [ ] Audit log schema آماده است
-   [ ] API Key Leak Runbook آماده است
-   [ ] Vault + HSM/KMS برای production keys تعریف شده

### ۲۵.۴ چک‌لیست تست و کیفیت

-   [ ] Unit tests برای منطق ریسک (≥ ۸۰٪ برای MVP، ≥ ۹۰٪ برای
    production)
-   [ ] Integration tests آماده‌اند
-   [ ] State machine tests آماده‌اند
-   [ ] Property-based tests آماده‌اند
-   [ ] Chaos Engineering checklist تعریف شده (۷ آزمون حداقل)
-   [ ] Fire Drill برای Kill Switch تعریف شده

### ۲۵.۵ چک‌لیست عملیاتی

-   [ ] SLA و SLO تعریف شده
-   [ ] RTO و RPO تعریف شده
-   [ ] Error budget policy تعریف شده
-   [ ] Incident severity levels تعریف شده
-   [ ] Operational runbooks مستند شده (۱۰ نقطه شکست)
-   [ ] User Approval Timeout در IPS تعریف شده
-   [ ] Feature flag برای قابلیت‌های پرریسک
-   [ ] Plan rollback برای هر migration و release

### ۲۵.۶ چک‌لیست تطبیق و حاکمیت داده

-   [ ] مشاوره حقوقی قبل از production
-   [ ] Data classification تعریف شده
-   [ ] Data retention policy تعریف شده
-   [ ] Encryption at-rest و in-transit
-   [ ] User rights تعریف شده
-   [ ] Wallex/Nobitex API امنیت مستند شده
-   [ ] Compliance checklist کامل شده

### ۲۵.۷ چک‌لیست مدل و ML

-   [ ] Baseline Model (rule-based) تعریف شده
-   [ ] Shadow Mode framework طراحی شده
-   [ ] Promotion criteria تعریف شده
-   [ ] Rollback criteria تعریف شده
-   [ ] A/B Testing framework طراحی شده
-   [ ] Model governance schema تعریف شده

### ۲۵.۸ چک‌لیست UI/UX

-   [ ] PWA با offline strategy تعریف شده
-   [ ] Mobile-first UX معیارها تعریف شده
-   [ ] Visual Audit UI برای سیگنال‌ها طراحی شده

### ۲۵.۹ چک‌لیست MVP-0

-   [ ] MVP-0 scope تعریف شده (single user، single exchange،
    Python-only)
-   [ ] Paper Trading با Docker Network Isolation پیاده شده
-   [ ] Kill Switch مستقل و قابل تست است
-   [ ] Baseline Metrics قابل محاسبه است
-   [ ] Team-size assumptions مستند شده

------------------------------------------------------------------------

## ۲۶. اولویت‌های نهایی محصول

پنج اصل بنیادین:

1.  **تأیید صریح کاربر:** هر اقدام نیازمند تأیید آگاهانه با پارامترهای
    دقیق.
2.  **حفظ سرمایه بر بازدهی:** مدیریت ریسک بر استراتژی اولویت دارد. Kill
    Switch مستقل.
3.  **قابل توضیح و قابل تست:** هر تصمیم با دلیل و عدم‌قطعیت. Visual Audit
    UI.
4.  **امن و قابل ممیزی:** Vault+HSM، RBAC، audit trail، least privilege.
5.  **مقیاس‌پذیر و تدریجی:** MVP-0 کوچک → Post-MVP گسترش. Go، ML،
    Multi-tenancy فقط پس از اثبات ارزش.

------------------------------------------------------------------------

## نتیجه‌گیری

این سند نسخه ۴.۳، بر مبنای نسخه‌های ۴.۱ و ۴.۲ و وصله نهایی G0 تنظیم شده است. محور اصلی: **کاهش scope برای MVP-0، جداسازی محیطی،
جایگزینی JEV با Baseline Metrics، و بستن چهار شکاف بلاک‌کننده G0 در Worker Lifecycle، Kill Switch، Authentication/Authorization و Retry Policy.**

  معیار                                مقدار
  ------------------------------------ ------------------------------------------------
  نسخه                                 ۴.۳ (G0 Blocker Closure)
  بخش‌ها                                ۲۶ بخش اصلی
  نقاط ضعف تیم فنی (دومین بازبینی)     ۹ + ۱ مورد = ۱۰ مورد (همه حل‌شده)
  پیشنهادات تیم فنی                    ۷ مورد (همه انجام‌شده)
  MVP-0 تعریف شده                      ✅ (single user، single exchange، Python-only)
  Go در MVP                            ❌ حذف شد
  JEV در MVP                           ❌ حذف شد، Baseline Metrics جایگزین
  Paper Trading با Network Isolation   ✅
  Kill Switch با ماتریس اختیار         ✅
  PWA با offline strategy              ✅
  RLS با Benchmark Gate                ✅
  API Key Leak Runbook                 ✅
  Baseline Model                       ✅
  Chaos Engineering Checklist          ✅
  One-Page Runbooks                    ✅
  User Approval Timeout SLA            ✅
  Visual Audit UI                      ✅
  Wallex/Nobitex مستند                 ✅

**این سند آماده ارزیابی نهایی تیم فنی پیش از آغاز کدنویسی است.**

------------------------------------------------------------------------

## منابع تحقیقاتی و مستندات

### معماری و Stack فناوری

-   [Best Programming Languages for Algorithmic
    Trading](https://www.luxalgo.com/blog/best-programming-languages-for-algorithmic-trading/)
    --- LuxAlgo
-   [Best Programming Language for Algorithmic Trading
    Systems](https://www.quantstart.com/articles/Best-Programming-Language-for-Algorithmic-Trading-Systems/)
    --- QuantStart
-   [Go vs Python for Trading
    Bots](https://usewisp.dev/blog/posts/go-vs-python-trading-bots) ---
    Wisp.dev

### SLA، RTO و RPO

-   [RTO vs RPO: Key
    Differences](https://www.sentinelone.com/cybersecurity-101/cloud-security/rto-vs-rpo/)
    --- SentinelOne
-   [RTO vs RPO: How To Set
    Targets](https://www.veeam.com/blog/recovery-time-recovery-point-objectives.html)
    --- Veeam
-   [Disaster Recovery Planning for Algorithmic
    Trading](https://breakingalpha.io/insights/disaster-recovery-planning-algorithmic-trading-operations)
    --- BreakingAlpha

### Multi-tenancy و Data Isolation

-   [Multi Tenant Security Cheat
    Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)
    --- OWASP
-   [Multi-Tenant FinTech SaaS: Data
    Isolation](https://tanujgarg.com/blog/multi-tenant-fintech-data-isolation-architecture)
    --- Tanuj Garg
-   [Why We Stopped Using Row-Level Security After 1M
    Rows](https://dev.to/canu/why-we-stopped-using-row-level-security-after-1m-rows-4dpb)
    --- dev.to
-   [Row Level Security
    performance](https://supabase.com/docs/guides/database/postgres/row-level-security-performance)
    --- Supabase
-   [RLS sounds great until it
    isn't](https://planetscale.com/blog/rls-sounds-great-until-it-isnt)
    --- PlanetScale

### Shadow Mode و Model Lifecycle

-   [Deployment --- Shadow
    Mode](https://docs.aws.amazon.com/prescriptive-guidance/latest/ml-operations-planning/deployment.html)
    --- AWS
-   [ML Lifecycle
    Management](https://mlflow.org/articles/tags/machine-learning-lifecycle/)
    --- MLflow
-   [Implementing Shadow
    Mode](https://www.systemoverflow.com/learn/ml-infrastructure-mlops/shadow-mode-deployment/implementing-shadow-mode-mirroring-isolation-and-promotion-criteria)
    --- SystemOverflow
-   [Shadow Deployment for ML
    Models](https://atlan.com/know/shadow-deployment-for-ml-models/) ---
    Atlan

### Stress Testing و Monte Carlo

-   [Quantifying Crypto Portfolio
    Risk](https://ar5iv.labs.arxiv.org/html/2507.08915) --- arXiv
-   [Monte Carlo Simulation for Crypto
    Strategies](https://docs.volaticloud.com/docs/simulations/overview)
    --- VolatiCloud

### Position Sizing و Kelly Criterion

-   [Mastering the Kelly Criterion for
    Crypto](https://www.lbank.com/explore/mastering-the-kelly-criterion-for-smarter-crypto-risk-management)
    --- LBank
-   [Best Crypto Portfolio Allocation
    2026](https://bitcoinfoundation.org/news/trading/how-to-build-a-profitable-crypto-portfolio/)
    --- Bitcoin Foundation

### Compliance و Regulatory (ایران)

-   [Central bank approves regulatory
    framework](https://www.tehrantimes.com/news/507174/Central-bank-approves-regulatory-framework-for-cryptocurrencies)
    --- Tehran Times
-   [Beyond the headlines of Iran's crypto
    usage](https://crystalintelligence.com/investigations/beyond-the-headlines-of-irans-crypto-usage/)
    --- Crystal Intelligence
-   [Iran Clears Way for Crypto Investment
    Funds](https://financialtribune.com/node/119424) --- Financial
    Tribune
-   [Iran Crypto Regulation
    2026](https://defi-intel.com/jurisdictions/ir/) --- DeFi Intel

### صرافی‌های داخلی ایران

-   [Wallex API Documentation](https://developers.wallex.ir/docs/) ---
    Wallex
-   [Wallex API Reference](https://api-docs.wallex.ir/) --- Wallex
-   [Nobitex API Key
    Guide](https://apidocs.nobitex.ir/api_key/api-key-guide) --- Nobitex
-   [Nobitex
    Security](https://apidocs.nobitex.ir/security/api-%D8%A7%D9%85%D9%86%DB%8C%D8%AA-%D9%86%D9%88%D8%A8%DB%8C%D8%AA%DA%A9%D8%B3)
    --- Nobitex
-   [Wallex API: endpoints, auth & code
    examples](https://singaporeapi.com/apis/wallex) --- SingaporeAPI

### Docker Network Isolation

-   [Docker Networking](https://docs.docker.com/engine/network/) ---
    Docker Docs
-   [Docker Sandboxes Security
    Model](https://docs.docker.com/ai/sandboxes/security/) --- Docker
-   [Packet filtering and
    firewalls](https://docs.docker.com/engine/network/packet-filtering-firewalls/)
    --- Docker

### PWA و Offline Strategy

-   [Best practices for
    PWAs](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Best_practices)
    --- MDN
-   [Service workers](https://web.dev/learn/pwa/service-workers) ---
    web.dev
-   [Progressive Web Apps:
    Offline-First](https://msphere.io/insights/progressive-web-apps-offline/)
    --- Metasphere
-   [PWAs 2025: Fast, Offline, and
    Reliable](https://blog.madrigan.com/blog/202511251047/) --- Madrigan

### Chaos Engineering

-   [Continuous chaos engineering experiment
    lifecycle](https://docs.aws.amazon.com/prescriptive-guidance/latest/chaos-engineering-on-aws/lifecycle.html)
    --- AWS
-   [Chaos Engineering for Financial
    Services](https://www.gremlin.com/whitepapers/chaos-engineering-for-financial-services)
    --- Gremlin
-   [What is Chaos
    Engineering?](https://www.ibm.com/think/topics/chaos-engineering)
    --- IBM

### Vault و HSM/KMS

-   [Vault Managed
    Keys](https://developer.hashicorp.com/vault/docs/enterprise/managed-keys)
    --- HashiCorp
-   [Vault
    HSM](https://developer.hashicorp.com/vault/docs/enterprise/hsm) ---
    HashiCorp
-   [Vault Key Management Secrets
    Engine](https://developer.hashicorp.com/vault/api-docs/secret/key-management)
    --- HashiCorp
-   [Streamlining cryptographic key management with
    Vault](https://www.hashicorp.com/en/blog/streamlining-cryptographic-key-management-with-hashicorp-vault)
    --- HashiCorp

### MVP و Fintech

-   [Fintech MVP Development: Step-by-Step
    Guide](https://www.aalpha.net/articles/how-to-build-a-fintech-mvp/)
    --- Aalpha
-   [Fintech MVP Development: Scope, Cost &
    Validation](https://sdk.finance/blog/how-to-build-a-fintech-mvp/)
    --- SDK Finance
-   [What is a Minimum Viable Product
    (MVP)?](https://www.atlassian.com/agile/product-management/minimum-viable-product)
    --- Atlassian

# Appendix --- MVP-0 Engineering Review Addendum

## Production Readiness Gate

این بخش مکمل فایل اصلی است و جایگزین آن نیست.

هدف: - جلوگیری از بازگشت به مراحل قبلی توسعه - ایجاد قرارداد روشن برای
تیم فنی - کنترل ریسک‌های مالی و عملیاتی

## G0 Approval Checklist

### Architecture

-   [ ] Architecture Decision Records Approved
-   [ ] MVP-0 Scope Frozen
-   [ ] Out of Scope Items Documented

### Database

-   [ ] Schema Approved
-   [ ] Migration Strategy Defined
-   [ ] Backup/Restore Tested

### Trading Safety

-   [ ] Order State Machine Approved
-   [ ] Synthetic Stop-Loss Persistent
-   [ ] Idempotency Defined
-   [ ] Exchange Reconciliation Defined

## Engineering Contract

اصول:

-   Correctness \> Complexity
-   Safety \> Automation
-   Auditability \> Speed

تغییر در موارد زیر نیازمند Review است:

-   API
-   Database
-   Events
-   Risk Rules
-   State Machines

## Database Contract

Source of Truth:

PostgreSQL

Redis فقط برای:

-   Cache
-   Lock
-   Rate Limit

Entityهای اصلی:

-   users
-   accounts
-   signals
-   orders
-   executions
-   positions
-   synthetic_stops
-   risk_events
-   audit_logs

## Synthetic Stop-Loss Requirements

-   Persistent State
-   Restart Recovery
-   Exchange Reconciliation
-   Idempotent Execution
-   Audit Trail

## Position Sizing Rule

Formula = Code = Tests

شامل:

-   Risk Budget
-   Stop Distance
-   Confidence Adjustment
-   Exposure Limits
-   Liquidity Constraints
-   Volatility Adjustment

## API Contract

اصول:

-   REST
-   JSON
-   UTC Timestamp
-   Versioned API
-   Structured Errors

## Event Model

Events:

-   SIGNAL_CREATED
-   SIGNAL_APPROVED
-   ORDER_CREATED
-   ORDER_SUBMITTED
-   ORDER_FILLED
-   POSITION_CREATED
-   STOP_REGISTERED
-   STOP_TRIGGERED
-   POSITION_CLOSED
-   RECONCILIATION_FAILED

## Testing Acceptance

قبل از Paper Trading:

-   Unit Tests
-   Integration Tests
-   Exchange Mock Tests
-   Failure Injection
-   Reconciliation Tests

قبل از Live:

-   Security Review
-   Backup Restore Test
-   Monitoring Validation
-   Kill Switch Test

## Development Gates

G0: Design Approval

G1: Foundation Ready

G2: Core Engine Ready

G3: Paper Trading Validation

G4: Controlled Live Approval

## Final Technical Review Status

-   Approved
-   Approved with Comments
-   Requires Changes

# Engineering Revision v3.0 --- Integrated Master Update

## Purpose

این نسخه اصلاحی، موارد اعلام‌شده در Production Readiness Review و
Technical Review را به صورت یکپارچه در سند اصلی ادغام می‌کند. اصلاحات به
صورت جایگزینی بخش‌های طراحی انجام شده و صرفاً Appendix نیست.

------------------------------------------------------------------------

# 1. MVP-0 Architecture Freeze

## Database Decision

MVP-0 uses:

-   PostgreSQL 16 as the system of record
-   Redis for transient operational state

TimescaleDB is excluded from MVP-0 and remains a Post-MVP evaluation
item only.

------------------------------------------------------------------------

# 2. Position Sizing Engineering Contract

اصل مرجع:

Formula = Implementation = Tests

فرمول نهایی:

    Position Size =
    MIN(
    N1 Risk Budget,
    N2 Stop Distance Limit,
    N3 Confidence Multiplier Adjusted Size,
    N4 Asset Exposure Limit,
    N5 Portfolio Exposure Limit,
    N6 User Maximum Notional
    )

هر تغییر در منطق اندازه پوزیشن باید همزمان در: - Mathematical
Definition - Source Implementation - Automated Tests

اعمال شود.

------------------------------------------------------------------------

# 3. Synthetic Stop-Loss Production Specification

## Requirements

Synthetic Stop-Loss must provide:

-   Persistent storage
-   Startup recovery
-   Exchange reconciliation
-   Idempotent execution
-   Duplicate order prevention

## State Machine

    REGISTERED
        |
    MONITORING
        |
    TRIGGERED
        |
    EXECUTING
        |
    EXECUTED
        |
    RECONCILED

Failure states:

    FAILED
    MANUAL_REVIEW
    CANCELLED

## Database Contract

``` sql
CREATE TABLE synthetic_stops (
    id UUID PRIMARY KEY,
    position_id UUID NOT NULL,
    stop_price NUMERIC NOT NULL,
    status VARCHAR(32) NOT NULL,
    idempotency_key VARCHAR(128) UNIQUE NOT NULL,
    execution_attempt_count INTEGER DEFAULT 0,
    last_execution_result TEXT,
    triggered_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
```

------------------------------------------------------------------------

# 4. Approval Workflow Atomic Contract

Approval transitions must be transactional.

Required flow:

    BEGIN TRANSACTION

    SELECT FOR UPDATE

    Validate Current State

    Validate Expiry

    Apply State Transition

    Create Audit Record

    COMMIT

Supported expiry states:

-   EXPIRED
-   PRICE_DRIFT_EXPIRED

------------------------------------------------------------------------

# 5. API Contract v1.0

Every endpoint must define:

-   Method
-   Path
-   Authentication
-   Request Schema
-   Response Schema
-   Error Contract

Core endpoints:

  Method   Path
  -------- ------------------------------
  POST     /api/v1/signals
  POST     /api/v1/signals/{id}/approve
  POST     /api/v1/orders
  GET      /api/v1/orders/{id}
  GET      /api/v1/positions

------------------------------------------------------------------------

# 6. Event Model Contract

All financial events use:

    event_id
    event_type
    version
    aggregate_id
    timestamp
    payload

Rules:

-   Versioned schemas
-   Immutable events
-   Retry safe consumers
-   Transactional outbox pattern

------------------------------------------------------------------------

# 7. ML Governance Reference

  Metric       Threshold             Action
  ------------ --------------------- ------------------
  PSI          \>0.2                 Drift Review
  KS Test      p \< 0.05             Drift Review
  Error Rate   \>5%                  Alert
  Sharpe       Baseline Comparison   Promotion Review

------------------------------------------------------------------------

# 8. Kill Switch Operational Policy

  Condition         Action
  ----------------- --------------------------
  Open Order        Cancel and verify
  Partial Fill      Reconcile
  Filled Position   Apply risk policy
  Active Stop       Disable safely and audit
  Unknown State     Manual review

------------------------------------------------------------------------

# 9. Engineering Change Traceability

  Review Finding             Resolution
  -------------------------- -------------------------------------------
  Stop Loss persistence      Added persistent state and reconciliation
  Position sizing mismatch   Added N1-N6 reference formula
  Approval race condition    Added atomic transition contract
  TimescaleDB conflict       Removed from MVP-0
  API gap                    Added API Contract
  Event gap                  Added Event Model
  Kill Switch gap            Added operational policy

------------------------------------------------------------------------

# Quality Gate

Before MVP-0 implementation:

-   Architecture approval required
-   Database migration reviewed
-   API contract frozen
-   Event schema frozen
-   Risk engine tests passed
-   Recovery scenarios validated

# v3.1 G0 Correction Integration --- Final Merged Revision

## Revision Purpose

این بخش به‌عنوان اصلاحات ادغام‌شده در Master Package اعمال شده است. این
موارد بخشی از سند اصلی محسوب می‌شوند و صرفاً Patch یا Appendix مستقل
نیستند.

------------------------------------------------------------------------

# Architecture Freeze Correction

## MVP-0 Active Architecture

    User
     |
    API Layer
     |
    Approval Engine
     |
    Risk Engine
     |
    Execution Engine
     |
    Exchange Adapter
     |
    Exchange API


    Infrastructure:
    - PostgreSQL 16
    - Redis 7
    - Docker Compose

## Explicitly Excluded From MVP-0

-   TimescaleDB
-   Vault
-   Consul

موارد فوق فقط در Roadmap مربوط به Post-MVP نگهداری می‌شوند.

------------------------------------------------------------------------

# Synthetic Stop-Loss Unified Engineering Contract

## Implementation Rule

پیاده‌سازی in-memory به‌عنوان Source of Truth منسوخ است.

Source of Truth:

PostgreSQL synthetic_stops table

## Required Capabilities

-   Persistent State
-   Startup Recovery
-   Exchange Reconciliation
-   Idempotent Execution
-   Duplicate Order Prevention

## SyntheticStopLossManager Contract

``` python
class SyntheticStopLossManager:

    def __init__(
        self,
        repository,
        exchange_adapter,
        current_timeframe
    ):
        self.repository = repository
        self.exchange_adapter = exchange_adapter
        self.current_timeframe = current_timeframe
```

`current_timeframe` باید از Strategy Configuration معتبر مقداردهی شود.

------------------------------------------------------------------------

# Position Sizing Formula = Code = Tests Contract

## Final Formula

    Position Size =
    MIN(
    N1,
    N2,
    N3,
    N4,
    N5,
    N6
    )

## Variable Mapping

  --------------------------------------------------------------------------
  Component               Python Variable            Test Parameter
  ----------------------- -------------------------- -----------------------
  N1 Risk Budget          risk_budget_limit          test_risk_budget

  N2 Stop Distance        stop_distance_limit        test_stop_distance

  N3 Confidence           confidence_multiplier      test_confidence
  Multiplier                                         

  N4 Asset Exposure       asset_exposure_limit       test_asset_limit

  N5 Portfolio Exposure   portfolio_exposure_limit   test_portfolio_limit

  N6 User Maximum         user_max_notional          test_user_limit
  Notional                                           
  --------------------------------------------------------------------------

هر تغییر باید همزمان در Formula، Code و Automated Tests اعمال شود.

------------------------------------------------------------------------

# Atomic Transition Implementation Reference

``` python
def try_transition(entity_id, expected_state, new_state):

    begin_transaction()

    entity = select_for_update(entity_id)

    if entity.state != expected_state:
        rollback()
        return False

    update_state(entity_id, new_state)

    create_audit_event()

    commit()

    return True
```

Return Contract:

-   True: transition committed
-   False: transition rejected

------------------------------------------------------------------------

# Frontend Decision

MVP-0 Frontend Standard:

## React

Reason:

-   mature ecosystem
-   broad engineering support
-   API-first compatibility

------------------------------------------------------------------------

# API Contract Completion

All APIs must include:

-   Version Strategy: `/api/v1/`
-   Request Schema
-   Response Schema
-   Authentication
-   Error Contract

Standard Error:

``` json
{
 "code":"INVALID_STATE",
 "message":"Invalid transition",
 "request_id":"uuid"
}
```

------------------------------------------------------------------------

# Transactional Outbox Contract

## Schema

``` sql
CREATE TABLE outbox_events (
 id UUID PRIMARY KEY,
 event_type VARCHAR(128),
 aggregate_id UUID,
 payload JSONB,
 status VARCHAR(32),
 created_at TIMESTAMPTZ,
 published_at TIMESTAMPTZ
);
```

Rules:

-   Consumer idempotency required
-   Duplicate event handling required
-   Retry-safe publishing required
-   Cleanup after retention period

------------------------------------------------------------------------

# Kill Switch Operational Procedure

Execution order:

1.  Freeze new order creation
2.  Cancel open orders
3.  Reconcile partially filled orders
4.  Apply position policy
5.  Disable active stop monitoring safely
6.  Create audit record
7.  Notify operator

Failure in any step:

    MANUAL_REVIEW

------------------------------------------------------------------------

# G0 Re-evaluation Checklist

Before approval:

-   Architecture diagram aligned with MVP-0 scope
-   No Post-MVP components in active architecture
-   Synthetic Stop-Loss persistence verified
-   N1-N6 mapping verified
-   Atomic transition implementation reviewed
-   API Contract frozen
-   Event Outbox contract reviewed
-   Kill Switch procedure tested

------------------------------------------------------------------------

# Engineering Change Traceability Update

  Finding                           Resolution
  --------------------------------- --------------------------------
  Architecture mismatch             MVP-0 diagram corrected
  In-memory stop logic              Persistent contract enforced
  current_timeframe runtime issue   Explicit initialization added
  N1-N6 mapping gap                 Variable/Test mapping added
  try_transition gap                Implementation reference added
  Frontend ambiguity                React selected
  API incompleteness                Contract requirements added
  Outbox incompleteness             Schema and rules added
  Kill Switch ambiguity             Ordered execution added


# v3.2 Final G0 Integration — Order State Machine and SLA Closure

> **Historical integration block:** The final executable clarifications for the four remaining G0 blockers are superseded by the v4.3 Final G0 Blocker Closure section appended below.

## Purpose
این بخش اصلاحات نهایی تاییدشده پس از بازبینی G0 را مستقیماً در Master Package ادغام می‌کند.

---

# Order State Machine Final Specification

## PROTECTION_FAILED Transition

وضعیت Protection Failure نباید بدون مسیر خروج باقی بماند.

Final transition:

```
PROTECTION_FAILED
        |
     Retry x3
        |
 CANCEL_POSITION
        |
    CANCELLED
```

Rule:
- پس از سه retry ناموفق، سیستم باید اقدام جبرانی را آغاز کند.
- وضعیت نهایی و Audit Event باید ثبت شود.

---

## PARTIALLY_FILLED Timeout Handling

Final transition:

```
PARTIALLY_FILLED
        |
      60s Timeout
        |
  FILLED_PARTIAL
        |
 CANCEL_REMAINDER
```

Rules:
- مقدار Filled حفظ می‌شود.
- بخش Remaining لغو می‌شود.
- نتیجه نهایی در Audit ثبت می‌شود.

---

## PRICE_DRIFT_EXPIRED Integration

Approval workflow:

```
PENDING_APPROVAL
        |
 Price Validation Failed
        |
PRICE_DRIFT_EXPIRED
```

این وضعیت بخشی از State Machine رسمی است.

---

# SLA Contract Finalization

## Downtime Definition

Downtime زمانی ثبت می‌شود که یکی از شرایط زیر رخ دهد:

- Health Check سرویس اصلی Fail شود.
- API قادر به پردازش درخواست معتبر نباشد.
- Error Rate از Threshold تعریف‌شده عبور کند.

---

## Endpoint Latency SLA

| Component | Target |
|---|---|
| Kill Switch | p99 < 50ms |
| Signal Approval | p99 < 200ms |
| Standard API | p99 < 200ms |

---

## Exchange Dependency Failure Policy

در صورت عدم دسترسی Exchange API:

1. Retry طبق Policy
2. توقف ایجاد سفارش جدید
3. حفظ وضعیت جاری
4. اجرای Protection Rules در شرایط لازم
5. Manual Review در شرایط بحرانی

---

# G0 Final Acceptance Update

Closed:

- Protection failure transition
- Partial fill timeout behavior
- PRICE_DRIFT_EXPIRED integration
- SLA measurement definition
- Endpoint latency classification
- Exchange failure policy

Status:

READY FOR G0 FINAL REVIEW

---

# v4.3 Final G0 Blocker Closure — Implementation Contracts

این بخش نسخه اجرایی نهایی قراردادهای موردنیاز برای بستن چهار شکاف بلاک‌کننده G0 است. در صورت تعارض با متن‌های قبلی، این بخش برای همین چهار موضوع **مرجع نهایی اجرایی** است.

## 1. Background Worker Lifecycle Contract

### 1.1 معماری اجرا

در MVP-0، workerها در همان فرآیند FastAPI و با `asyncio` اجرا می‌شوند. برای جلوگیری از اجرای چندباره workerها، سرویس MVP-0 فقط با **یک application process** اجرا می‌شود:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

استفاده از بیش از یک Uvicorn/Gunicorn worker در MVP-0 مجاز نیست، زیرا باعث اجرای duplicate در scheduler/monitorها می‌شود.

### 1.2 Workerهای الزامی

| Worker | Trigger | Interval | مسئولیت | Failure Policy |
|---|---|---:|---|---|
| `approval_timeout_worker` | Startup | هر 5 ثانیه | پیدا کردن `PENDING_APPROVAL` و اجرای `check_timeout()` | Freeze new execution + Critical alert + Kill Switch |
| `synthetic_stop_worker` | Startup | بر اساس timeframe: `1H=30s`, `4H=60s`, `1D=300s` | اجرای `monitor_positions()` برای تمام Synthetic Stopهای فعال | Freeze new orders + Critical alert + Kill Switch |

`check_timeout()` دیگر صرفاً یک متد قابل فراخوانی نیست؛ این متد **باید توسط `approval_timeout_worker` به‌صورت دوره‌ای اجرا شود**.

`monitor_positions()` نیز worker مستقل منطقی خود را دارد و **نباید در هر request HTTP** اجرا شود.

### 1.3 FastAPI Lifespan

Startup و shutdown workerها باید با FastAPI lifespan مدیریت شود:

```python
from contextlib import asynccontextmanager
import asyncio

WORKER_TASKS: list[asyncio.Task] = []

@asynccontextmanager
async def lifespan(app):
    await recover_synthetic_stops_from_db()
    await reconcile_open_positions()

    WORKER_TASKS.extend([
        asyncio.create_task(approval_timeout_supervisor()),
        asyncio.create_task(synthetic_stop_supervisor()),
    ])

    try:
        yield
    finally:
        for task in WORKER_TASKS:
            task.cancel()
        await asyncio.gather(*WORKER_TASKS, return_exceptions=True)
        WORKER_TASKS.clear()
```

### 1.4 Supervisor و Fail-Safe

Supervisor باید crash شدن worker را تشخیص دهد. اگر worker پس از `CancelledError` به‌طور غیرعادی با exception خاتمه یابد:

1. یک `WORKER_FAILURE` در Audit Log ثبت شود.
2. Critical Notification ارسال شود.
3. ایجاد سفارش جدید فوراً freeze شود.
4. در **LIVE mode**، Kill Switch فعال شود.
5. در **PAPER mode**، execution متوقف و فقط وضعیت شبیه‌سازی حفظ شود.
6. worker تا زمانی که incident کنترل نشده است نباید silent restart شود.

### 1.5 Idempotency و Recovery

در startup:

- Synthetic Stopهای active از PostgreSQL بارگذاری شوند.
- پوزیشن‌های باز با Exchange reconciliation شوند.
- worker فقط پس از موفقیت recovery وارد حلقه عادی شود.
- اجرای restart نباید باعث ثبت Stop/Order تکراری شود؛ اجرای protection باید idempotent باشد.

### 1.6 Acceptance Tests

- [ ] با startup تنها یک instance از هر worker اجرا می‌شود.
- [ ] `check_timeout()` حداکثر هر 5 ثانیه یک‌بار بررسی می‌شود.
- [ ] Synthetic Stop بر اساس timeframe با intervalهای 30/60/300 ثانیه بررسی می‌شود.
- [ ] با crash شدن Stop worker، سفارش جدید freeze و Kill Switch فعال می‌شود (LIVE).
- [ ] restart سرویس منجر به بازیابی Stopهای persistent و reconciliation می‌شود.
- [ ] اجرای endpointهای HTTP باعث ساخت worker جدید نمی‌شود.

---

## 2. Kill Switch REST Endpoint Contract

### 2.1 Endpoint

```http
POST /api/v1/system/emergency-stop
Authorization: Bearer <MVP0_ADMIN_API_KEY>
Content-Type: application/json
```

Request:

```json
{
  "reason": "manual emergency stop"
}
```

`reason` الزامی، trim شده و با حداقل 3 و حداکثر 500 کاراکتر است.

Success response (`200`):

```json
{
  "status": "activated",
  "timestamp": "2026-10-02T08:00:00Z",
  "request_id": "uuid"
}
```

Idempotent already-active response (`200`):

```json
{
  "status": "already_active",
  "timestamp": "2026-10-02T08:00:01Z",
  "request_id": "uuid"
}
```

### 2.2 Authorization

- Endpoint فقط با `MVP0_ADMIN_API_KEY` مجاز است.
- API Key معمولی (`MVP0_API_KEY`) برای emergency-stop کافی نیست.
- ارسال role از طریق header یا request body، منبع اعتبار authorization نیست.
- مقایسه API Key باید constant-time باشد.
- API Key هرگز در log، audit payload یا response ثبت نمی‌شود.

### 2.3 اجرای عملیاتی

Endpoint باید `kill_switch.activate(reason=...)` را صدا بزند و همان ترتیب عملیاتی تثبیت‌شده را اجرا کند:

1. Freeze new order creation
2. Cancel open orders
3. Reconcile partially filled orders
4. Apply position policy
5. Disable active stop monitoring safely
6. Create audit record
7. Notify operator

خطای هر مرحله:

```text
MANUAL_REVIEW
```

### 2.4 Error Contract

| HTTP | Code | Meaning |
|---:|---|---|
| 400 | `INVALID_REQUEST` | بدنه یا `reason` نامعتبر |
| 401 | `UNAUTHORIZED` | Bearer token وجود ندارد/نامعتبر است |
| 403 | `FORBIDDEN` | API Key معتبر است ولی Admin permission ندارد |
| 409 | `KILL_SWITCH_CONFLICT` | وضعیت فعلی با activation ناسازگار است |
| 429 | `RATE_LIMITED` | عبور از محدودیت درخواست |
| 503 | `SYSTEM_UNAVAILABLE` | سیستم قادر به اجرای emergency procedure نیست |

قالب پاسخ خطا همان contract استاندارد سند است:

```json
{
  "code": "UNAUTHORIZED",
  "message": "Authentication failed",
  "request_id": "uuid"
}
```

### 2.5 Health Endpoint

برای monitoring، endpoint زیر بدون Authentication در دسترس است و فقط اطلاعات سلامت غیرحساس را بازمی‌گرداند:

```http
GET /healthz
```

نمونه پاسخ:

```json
{
  "status": "ok",
  "db": "ok",
  "redis": "ok",
  "timestamp": "2026-10-02T08:00:00Z"
}
```

`/healthz` نباید API Key، exchange credential، stack trace یا داده مالی بازگرداند.

---

## 3. Authentication Contract for `/api/v1/`

### 3.1 Scheme

تمام endpointهای `/api/v1/*` به‌جز استثنای صریح `GET /healthz` از **Static API Key Authentication** استفاده می‌کنند:

```http
Authorization: Bearer <token>
```

JWT/OAuth در MVP-0 خارج از scope است.

### 3.2 Keys

```text
MVP0_API_KEY        = key for normal API access
MVP0_ADMIN_API_KEY  = separate key for Admin-only operations
```

هر دو مقدار از environment/secret injection خوانده می‌شوند و در source code hard-code نمی‌شوند.

### 3.3 Middleware Rule

Authentication باید قبل از handler اجرا شود:

```python
async def require_api_key(authorization: str):
    token = extract_bearer_token(authorization)
    if constant_time_compare(token, settings.MVP0_ADMIN_API_KEY):
        return "admin"
    if constant_time_compare(token, settings.MVP0_API_KEY):
        return "operator"
    raise HTTPException(status_code=401, detail="Authentication failed")
```

Authorization سپس بر اساس endpoint انجام می‌شود:

- `operator` → read + normal authenticated API operations
- `admin` → operator permissions + admin-only operations such as emergency-stop

هیچ endpointی نباید role را از ورودی کاربر trust کند.

### 3.4 Security Requirements

- [ ] API Key در URL/query string ممنوع.
- [ ] API Key در log و error response ممنوع.
- [ ] `Authorization` header تنها محل ارسال credential است.
- [ ] API key rotation از طریق environment/secret update انجام می‌شود؛ نیازی به migration ندارد.
- [ ] تست 401 برای token missing/invalid و 403 برای token معتبر ولی insufficient privilege وجود دارد.
- [ ] تمامی mutationهای حساس audit شوند.

### 3.5 Core API Contract Update

| Method | Path | Auth |
|---|---|---|
| POST | `/api/v1/signals` | Bearer API Key |
| POST | `/api/v1/signals/{id}/approve` | Bearer API Key |
| POST | `/api/v1/orders` | Bearer API Key |
| GET | `/api/v1/orders/{id}` | Bearer API Key |
| GET | `/api/v1/positions` | Bearer API Key |
| POST | `/api/v1/system/emergency-stop` | Bearer **Admin** API Key |
| GET | `/healthz` | No Auth |

---

## 4. `PROTECTION_FAILED` Retry Contract

### 4.1 Retry Schedule

برای رفع ابهام، زمان‌ها **نسبت به زمان اولین failure** تعریف می‌شوند:

```text
Attempt 1: t = 0s   (immediate)
Attempt 2: t = 5s
Attempt 3: t = 15s
```

این schedule ثابت است و در MVP-0 exponential backoff نیست.

### 4.2 State Contract

```text
PROTECTION_FAILED
        |
   Retry Schedule
   0s / 5s / 15s
        |
   success? ---- yes ---> PROTECTED
        |
        no after Attempt 3
        v
  CANCEL_POSITION
        |
    CANCELLED
```

### 4.3 Rules

- Attempt 1 بدون sleep اجرا می‌شود.
- Attempt 2 پنج ثانیه پس از failure اولیه اجرا می‌شود.
- Attempt 3 پانزده ثانیه پس از failure اولیه اجرا می‌شود.
- هر attempt باید idempotent باشد و client/order identity تکراری ایجاد نکند.
- پس از failure نهایی، مسیر جبرانی `CANCEL_POSITION → CANCELLED` اجرا می‌شود.
- Final state + retry count + failure reason + timestamps در Audit Log ثبت می‌شوند.
- اگر cancellation نیز شکست خورد، وضعیت `MANUAL_REVIEW` ثبت و Critical Notification ارسال می‌شود.

### 4.4 Acceptance Tests

- [ ] تست زمان‌بندی دقیق `0s/5s/15s`.
- [ ] تست موفقیت در Attempt 2 → transition به `PROTECTED`.
- [ ] تست سه failure متوالی → `CANCEL_POSITION`.
- [ ] تست idempotent retry و عدم duplicate order.
- [ ] ثبت کامل audit برای هر attempt و final outcome.

---

# v4.3 G0 Final Acceptance Update

### Blockers Closed

- [x] Background Worker lifecycle, startup/shutdown, interval and crash policy
- [x] Kill Switch endpoint, authentication and Admin authorization
- [x] Authentication contract for `/api/v1/*`
- [x] `PROTECTION_FAILED` retry schedule (`0s/5s/15s`) and terminal path

### Scope Consistency Closed

- [x] MVP-0 architecture contains PostgreSQL + Redis only for the data/cache layer
- [x] TimescaleDB and Vault remain Post-MVP in the active MVP-0 scope
- [x] MVP-0 process model fixed to single application worker

### G0 Status

**BLOCKERS CLOSED — READY FOR FINAL G0 SIGN-OFF AND CONTROLLED IMPLEMENTATION.**

Final implementation gate remains conditional on the acceptance tests defined in this section and the existing test/quality gates of §9.

