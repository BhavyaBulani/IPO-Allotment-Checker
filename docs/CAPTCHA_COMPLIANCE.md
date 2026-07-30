# CAPTCHA-Solver Compliance Considerations

## Overview
This document outlines the legal and compliance considerations for using automated CAPTCHA solvers (e.g., 2Captcha, Anti-Captcha) or bypassing mechanisms when scraping registrar websites (Link Intime, KFin, Bigshare, MUFG) for IPO allotment statuses.

## 1. Terms of Service (ToS) Violations
Almost all registrar websites have explicit Terms of Service prohibiting:
- Automated scraping or bulk data extraction.
- Bypassing security measures, including CAPTCHAs and Rate Limiters.

**Risk:** Violating the ToS can lead to IP bans, suspension of linked brokerage accounts, or potential legal action from the registrars.

## 2. Data Privacy (DPDP Act / GDPR)
Registrar websites often host Personally Identifiable Information (PII) such as PAN numbers and Client Codes.
- Forwarding CAPTCHA challenges to 3rd-party solving services (which rely on human workers in various countries) can inadvertently expose metadata or context related to the query.
- Sending PAN data in headers or payloads to external solvers without obfuscation violates privacy regulations.

**Mitigation:** Only send the raw CAPTCHA image bytes to the solving service. Ensure that no PII (like PAN, DPID, Name) is transmitted to the CAPTCHA provider.

## 3. Rate Limiting and Fair Usage
Using an automated CAPTCHA solver dramatically increases the speed and volume of requests that can be sent to a registrar.
- Registrars may lack the infrastructure to handle thousands of concurrent requests per second.
- A Denial-of-Service (DoS) condition can be accidentally triggered.

**Mitigation:** The application MUST enforce strict rate limiting (e.g., `rate_limiter.py` pacing) and utilize connection pooling to remain within fair usage limits, regardless of whether a CAPTCHA solver is used.

## 4. Legal Grey Area
While using CAPTCHA solving services is technically feasible, their legal standing is highly ambiguous in many jurisdictions. 
- Some services have faced legal challenges from companies like Google and Cloudflare.
- The use of these services for commercial scraping operations can be considered a violation of the Computer Fraud and Abuse Act (CFAA) in the US, or the Information Technology Act in India, if unauthorized access is established.

## Recommendation
For the IPO Allotment Verification System, it is strongly recommended to:
1. **Prefer Manual Verification**: Use the internal `ManualCaptchaProvider` to prompt authorized operators to solve CAPTCHAs, keeping the interaction local and human-driven.
2. **Obtain API Access**: Where possible, negotiate direct B2B API access with registrars (e.g., Upstox API integration) to avoid scraping entirely.
3. **Use Solvers as a Last Resort**: If a 3rd-party solver is strictly necessary for business operations, ensure explicit legal counsel is obtained and all PII is scrubbed before transmission.
