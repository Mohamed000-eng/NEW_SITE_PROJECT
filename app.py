# app.py - كود Python لأتمتة إنشاء وإرسال الفواتير

from flask import Flask, request, render_template_string, redirect, url_for
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
from datetime import datetime

app = Flask(__name__)

# ----------------------------------------------------
# 🚨🚨🚨 يجب تغيير هذه المعلومات 🚨🚨🚨
# ----------------------------------------------------
# بيانات الإيميل الرسمي للمجموعة (المستخدمة في الإرسال)
EMAIL_ADDRESS = "abdelwanisgroup@gmail.com"  # الإيميل الذي سيستخدم للإرسال
EMAIL_PASSWORD = "YOUR_EMAIL_APP_PASSWORD"   # 🚨🚨🚨 يجب الحصول على كلمة مرور خاصة بالتطبيق من إعدادات الإيميل
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
# ----------------------------------------------------

# تنسيق HTML لصفحة النجاح (سنستخدمها للرد على العميل بعد الإرسال)
SUCCESS_PAGE_HTML = """
<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><title>تم الإرسال بنجاح</title>
<link rel="stylesheet" href="style.css"></head><body>
<div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
    <h1 style="color: #4CAF50;">✅ تم استلام طلبكم بنجاح!</h1>
    <p style="font-size: 1.2em;">جارٍ إنشاء الفاتورة المبدئية وإرسالها إلى الإيميل: <b>{{ email }}</b>.</p>
    <p>سيتم التواصل معكم قريباً عبر الواتساب: <b>{{ whatsapp }}</b> لتأكيد تفاصيل التوريد.</p>
    <a href="/" style="display: inline-block; margin-top: 20px; padding: 10px 20px; background-color: #004d40; color: white; text-decoration: none; border-radius: 5px;">العودة للصفحة الرئيسية</a>
</div>
</body></html>
"""

# دالة مساعدة لإنشاء ملف PDF للفاتورة
def create_invoice_pdf(data, pdf_path):
    c = canvas.Canvas(pdf_path, pagesize=A4)
    width, height = A4
    
    # رأس الفاتورة
    c.setFont('Helvetica-Bold', 24)
    c.drawString(width - 200, height - 50, "طلب فاتورة (EL.WADI)")

    # بيانات الشركة
    c.setFont('Helvetica', 10)
    c.drawString(50, height - 50, "مجموعة عبد الونيس للتوريد")
    c.drawString(50, height - 65, f"الإيميل: {EMAIL_ADDRESS}")
    c.drawString(50, height - 80, "الهاتف: 01229395435")

    # بيانات العميل
    c.setFont('Helvetica-Bold', 12)
    c.drawString(50, height - 120, "بيانات العميل:")
    c.setFont('Helvetica', 10)
    c.drawString(50, height - 135, f"اسم الشركة: {data['company_name']}")
    c.drawString(50, height - 150, f"الإيميل: {data['email']}")
    c.drawString(50, height - 165, f"واتساب: {data['whatsapp_number']}")
    c.drawString(50, height - 180, f"العنوان: {data['shipping_address']}")

    # جدول المنتجات المطلوبة
    items = [
        ["المنتج", "الكمية المطلوبة", "ملاحظات (لا يوجد سعر مبدئي)"]
    ]
    
    # إضافة المنتجات من النموذج
    for i in range(1, 6):
        product_key = f'product_{i}'
        quantity_key = f'quantity_{i}'
        
        product = data.get(product_key)
        quantity = data.get(quantity_key)
        
        # التأكد من أن المنتج تم اختياره والكمية أكبر من الصفر
        if product and product != "--- اختر المنتج (اختياري) ---" and quantity:
            try:
                quantity_val = int(quantity)
                if quantity_val > 0:
                    items.append([product, str(quantity_val), "سيتم التواصل لتحديد السعر"])
            except ValueError:
                pass # تجاهل إذا كانت الكمية غير صحيحة

    # تصميم الجدول
    table = Table(items, colWidths=[150, 100, 200])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#004d40')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
    ]))

    # رسم الجدول في الصفحة
    table.wrapOn(c, width, height)
    table.drawOn(c, 50, height - 250 - len(items) * 20)
    
    # ملاحظة هامة
    c.setFont('Helvetica-Bold', 10)
    c.setFillColor(colors.red)
    c.drawString(50, 50, "هذه فاتورة مبدئية لطلب التوريد ولا تمثل الفاتورة النهائية.")
    c.drawString(50, 35, "سيتم التواصل من قبل قسم المبيعات عبر الواتساب للتسعير والتوريد.")

    c.showPage()
    c.save()

# دالة مساعدة لإرسال الإيميل
def send_email_with_attachment(to_email, subject, body, attachment_path):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))

    # إرفاق ملف PDF
    with open(attachment_path, "rb") as attach_file:
        part = MIMEApplication(attach_file.read(), Name=os.path.basename(attachment_path))
    
    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
    msg.attach(part)

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        
        # إرسال نسخة للبريد الإداري أيضاً
        server.sendmail(EMAIL_ADDRESS, "abdelwanisgroup@gmail.com", msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


# المسار الذي يستقبل بيانات نموذج طلب الفاتورة
@app.route('/submit_invoice', methods=['POST'])
def submit_invoice():
    if request.method == 'POST':
        data = request.form.to_dict()
        
        # 1. إنشاء ملف PDF للفاتورة
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        pdf_filename = f"Invoice_{data['company_name']}_{timestamp}.pdf"
        pdf_path = os.path.join("/tmp", pdf_filename) # حفظ مؤقت في /tmp

        # يجب التأكد من تثبيت الخط العربي المناسب لـ reportlab إذا كنت تريد كتابة النص العربي مباشرة في PDF
        # حالياً، الكود يستخدم الخط الافتراضي (قد تظهر الحروف مقلوبة بدون تثبيت الخط)

        create_invoice_pdf(data, pdf_path)
        
        # 2. إرسال الإيميل للعميل ونسخة للمدير
        subject = f"طلب فاتورة جديد من العميل: {data['company_name']}"
        body_to_customer = f"""
        مرحباً {data['company_name']},

        نشكركم على طلبكم. مرفق نسخة من طلب التوريد المبدئي رقم {timestamp}.
        يرجى مراجعة التفاصيل.

        سيتم التواصل معكم على رقم الواتساب: {data['whatsapp_number']} خلال 24 ساعة لتأكيد الأسعار النهائية وتفاصيل الشحن.

        مع خالص التقدير،
        فريق مبيعات مجموعة عبد الونيس (EL.WADI)
        """
        
        send_email_with_attachment(data['email'], subject, body_to_customer, pdf_path)
        
        # 3. حذف الملف المؤقت
        os.remove(pdf_path)

        # 4. توجيه العميل لصفحة النجاح
        return render_template_string(SUCCESS_PAGE_HTML, email=data['email'], whatsapp=data['whatsapp_number'])

@app.route('/')
def home():
    # في الخادم الحقيقي، يجب أن توجه هذا إلى ملف index.html أو يتم التعامل معه من قبل GitHub Pages
    return redirect("https://github.com/YourUsername/YourRepoName") # رابط مؤقت

if __name__ == '__main__':
    # لتشغيل الكود في البيئة المحلية لاختباره (لن يعمل هنا بشكل كامل)
    app.run(host='0.0.0.0', port=5000)

