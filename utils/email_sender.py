import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
import threading

def send_otp_email_sync(sender_email, sender_password, receiver_email, otp):
    try:
        msg = MIMEText("Placeholder", "html")  # We'll set the payload directly later
        msg['From'] = f"FlatSync Admin <{sender_email}>"
        msg['To'] = receiver_email
        msg['Subject'] = "Security Alert: FlatSync Authorization Code"
        
        # Beautiful HTML Version
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    background-color: #f1f5f9;
                    margin: 0;
                    padding: 0;
                    -webkit-font-smoothing: antialiased;
                }}
                .container {{
                    max-width: 500px;
                    margin: 40px auto;
                    background: #ffffff;
                    border-radius: 24px;
                    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.08);
                    overflow: hidden;
                    border: 1px solid #e2e8f0;
                }}
                .header {{
                    background: linear-gradient(135deg, #10b981, #059669);
                    color: white;
                    padding: 40px 20px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 900;
                    letter-spacing: 2px;
                    text-transform: uppercase;
                }}
                .content {{
                    padding: 40px;
                    color: #334155;
                    line-height: 1.6;
                    text-align: center;
                }}
                .otp-box {{
                    background: #f8fafc;
                    border: 2px dashed #10b981;
                    border-radius: 16px;
                    padding: 20px 10px;
                    margin: 30px auto;
                    font-size: 28px;
                    font-weight: 900;
                    color: #059669;
                    letter-spacing: 8px;
                    text-shadow: 0 2px 4px rgba(16, 185, 129, 0.2);
                    white-space: nowrap;
                    width: 80%;
                    max-width: 300px;
                }}
                .footer {{
                    background: #f8fafc;
                    padding: 24px;
                    text-align: center;
                    font-size: 11px;
                    color: #94a3b8;
                    border-top: 1px solid #f1f5f9;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>FlatSync</h1>
                    <div style="font-size: 10px; opacity: 0.9; letter-spacing: 5px; margin-top: 8px;">SECURITY CLEARANCE</div>
                </div>
                <div class="content">
                    <h2 style="margin-top: 0; color: #0f172a; font-size: 20px;">Authorization Required</h2>
                    <p style="color: #64748b; font-size: 14px;">An access request was made to the Administrative Gateway. Please use the verification code below to confirm your identity.</p>
                    
                    <div class="otp-box">
                        {otp}
                    </div>
                    
                    <p style="font-size: 13px; color: #ef4444; font-weight: bold;">This code is highly confidential.</p>
                    
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 30px;">
                        If you did not initiate this login request, your credentials may be compromised.
                    </div>
                </div>
                <div class="footer">
                    &copy; FlatSync System Management
                </div>
            </div>
        </body>
        </html>
        """

        # Set the HTML payload
        msg.set_payload(html_body)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        server.quit()
        print("OTP email sent successfully.")
    except Exception as e:
        print(f"Error sending OTP email: {e}")

def send_otp_email(otp):
    """ Spawns a background thread to send the OTP email """
    app = current_app._get_current_object()
    sender_email = app.config.get('SMTP_EMAIL')
    sender_password = app.config.get('SMTP_PASSWORD')
    receiver_email = app.config.get('ADMIN_EMAIL')
    
    if not sender_email or not sender_password or not receiver_email:
        print("Missing email configuration for OTP. Please check config.json.")
        return
        
    thread = threading.Thread(target=send_otp_email_sync, args=(sender_email, sender_password, receiver_email, otp))
    thread.daemon = True
    thread.start()
