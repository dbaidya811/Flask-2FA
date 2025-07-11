# 2FA REST API Documentation

This API allows developers to integrate Two-Factor Authentication (2FA) into their own websites or applications using your service.

---

## Quick Start for Developers

1. **Register an account** on the dashboard.
2. **Login** and go to your dashboard.
3. **Generate your API Key** by clicking the 'Generate API Key' button.
4. **Scan the QR code** (if prompted) with Google Authenticator or a similar app.
5. **Use your API Key** in the `X-API-KEY` header for all protected API requests.
6. **Refer to the API Documentation** for endpoint details and example requests.

---

## Authentication
- **API Key**: Each user receives a unique API Key after registration/login, visible on their dashboard.
- **Usage**: For protected endpoints, include the API Key in the HTTP header:
  - `X-API-KEY: <your_api_key>`

---

## Endpoints

### 1. Register User
**POST** `/api/register`

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```
**Response:**
```json
{
  "success": true,
  "message": "Registration successful!",
  "user_id": 1
}
```

---

### 2. Login User
**POST** `/api/login`

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```
**Response:**
```json
{
  "success": true,
  "message": "Login successful. Proceed to 2FA.",
  "user_id": 1
}
```

---

### 3. Initialize 2FA (Get QR Code & Secret)
**POST** `/api/2fa/init`

**Request Body:**
```json
{
  "user_id": 1
}
```
**Response:**
```json
{
  "success": true,
  "secret": "JBSWY3DPEHPK3PXP",
  "qr_b64": "<base64-encoded-png>",
  "otpauth_url": "otpauth://totp/Flask2FA:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=Flask2FA"
}
```
- `qr_b64`: Base64-encoded PNG image for Google Authenticator.
- `secret`: Manual entry for authenticator apps.
- `otpauth_url`: For direct integration with authenticator apps.

---

### 4. Verify OTP (2FA)
**POST** `/api/2fa/verify`

**Headers:**
```
X-API-KEY: <your_api_key>
Content-Type: application/json
```
**Request Body:**
```json
{
  "otp": "123456"
}
```
**Response (Success):**
```json
{
  "success": true,
  "message": "2FA verification successful!"
}
```
**Response (Failure):**
```json
{
  "success": false,
  "message": "Invalid OTP."
}
```

---

## Example: Verify OTP with cURL
```bash
curl -X POST https://yourdomain.com/api/2fa/verify \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <your_api_key>" \
  -d '{"otp": "123456"}'
```

---

## Common Issues & Solutions

**Issue:** `Invalid OTP.`
- **Solution:** Ensure your device time is correct and you are using the latest OTP from your authenticator app.

**Issue:** `API Key required in X-API-KEY header.`
- **Solution:** Generate your API Key from the dashboard and include it in the request header.

**Issue:** `Invalid API Key or TOTP not set.`
- **Solution:** Make sure you have generated your API Key and completed 2FA setup.

**Issue:** Cannot scan QR code
- **Solution:** Use the manual secret to add the account in your authenticator app.

**Issue:** Still having trouble?
- **Solution:** Contact support or check the dashboard for more help.

---

## Notes
- Always keep your API Key secret.
- The QR code and secret should be given to the user only once (during setup).
- OTPs are time-based and valid for 30 seconds (with a ±30s window).
- If you lose your API Key, generate a new one from your dashboard.

---

For further help, contact support or refer to the dashboard for your API Key and endpoint URL. 