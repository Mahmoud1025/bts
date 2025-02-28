from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from PIL import Image, ImageOps, ImageDraw, ImageFilter, ImageFont
import os
import asyncio
import uuid
from arabic_reshaper import arabic_reshaper
from bidi.algorithm import get_display

# المتغيرات
IMAGE_WIDTH = 626
IMAGE_HEIGHT = 626
STROKE_SIZE = 10
STROKE_COLOR = (208, 158, 59)
SHADOW_OPACITY = 100
SHADOW_BLUR_RADIUS = 10
ZOOM_LEVEL = 1.0

# Y_OFFSET لكل قالب
Y_OFFSET_TEMPLATE_1 = 170  # للقالب الأول
Y_OFFSET_TEMPLATE_2 = 80   # للقالب الثاني

# حجم القناع (يمكن تعديله حسب الحاجة)
MASK_WIDTH = 406  # عرض القناع
MASK_HEIGHT = 426  # ارتفاع القناع

# حجم الإطار الذهبي (نسبة إلى حجم الشكل الداخلي)
STROKE_SCALE = 1.01  # 1.0 يعني نفس الحجم، 1.1 يعني أكبر بنسبة 10%

# متغيرات الفنوس
FANOS_WIDTH = 52  # عرض الفنوس
FANOS_HEIGHT = 222  # طول الفنوس
FANOS_Y_OFFSET = -170  # تحريك الفنوس لأعلى أو لأسفل (قيمة موجبة لأسفل، سالبة لأعلى)

# مسارات القوالب
TEMPLATE_1_PATH = "template1.png"  # القالب الأول
TEMPLATE_2_PATH = "template2.png"  # القالب الثاني (بدون إطار ذهبي)
TEMPLATE_1_MASK_PATH = "template1_mask.png"  # قناع القالب الأول (الشكل الدائري)
TEMPLATE_1_STROKE_PATH = "template1_stroke.png"  # الإطار الذهبي للقالب الأول
TEMPLATE_2_MASK_PATH = "template2_mask.png"  # قناع القالب الثاني (الشكل الداخلي فقط)
TEMPLATE_2_STROKE_PATH = "template2_stroke.png"  # الإطار الذهبي فقط
FANOS_PATH = "fanos.png"  # شكل الفنوس

# متغيرات النص
TEXT_Y_OFFSET = -226  # تحريك النص لأعلى أو لأسفل (قيمة موجبة لأسفل، سالبة لأعلى)
FONT_SIZE = 44.3  # حجم الخط
FONT_WIDTH = 1.0  # عرض الخط (1.0 يعني العرض الطبيعي)
FONT_HEIGHT = 1.0  # ارتفاع الخط (1.0 يعني الارتفاع الطبيعي)

def create_card(user_photo_path, user_id, template_path, user_name=None):
    try:
        template = Image.open(template_path).convert("RGBA")
        user_photo = Image.open(user_photo_path).convert("RGBA")

        new_width = int(IMAGE_WIDTH * ZOOM_LEVEL)
        new_height = int(IMAGE_HEIGHT * ZOOM_LEVEL)
        new_size = (new_width, new_height)

        user_photo = ImageOps.fit(user_photo, new_size, method=Image.LANCZOS, centering=(0.5, 0.5))

        if template_path == TEMPLATE_1_PATH:
            # القالب الأول: صورة داخل دائرة باستخدام قناع مسبق الصنع
            mask = Image.open(TEMPLATE_1_MASK_PATH).convert("L")  # قناع القالب الأول
            mask = mask.resize(new_size, Image.LANCZOS)  # تغيير حجم القناع

            # تغيير حجم الصورة لتناسب حجم القناع
            user_photo = user_photo.resize(new_size, Image.LANCZOS)

            # تطبيق القناع على صورة المستخدم (فقط على الشكل الدائري)
            user_photo.putalpha(mask)

            # تحديد موقع الصورة في القالب
            x_offset = (template.width - new_size[0]) // 2
            y_offset = Y_OFFSET_TEMPLATE_1  # استخدام Y_OFFSET للقالب الأول

            # إنشاء طبقة جديدة للصورة مع الحفاظ على الإطار الذهبي
            combined_image = Image.new("RGBA", template.size, (0, 0, 0, 0))
            combined_image.paste(user_photo, (x_offset, y_offset), user_photo)

            # دمج الصورة مع القالب (مع الحفاظ على الإطار الذهبي)
            template.paste(combined_image, (0, 0), combined_image)

            # تحميل الإطار الذهبي كطبقة منفصلة
            stroke_layer = Image.open(TEMPLATE_1_STROKE_PATH).convert("RGBA")

            # تغيير حجم الإطار الذهبي بناءً على STROKE_SCALE
            stroke_width = int(new_size[0] * STROKE_SCALE)
            stroke_height = int(new_size[1] * STROKE_SCALE)
            stroke_layer = stroke_layer.resize((stroke_width, stroke_height), Image.LANCZOS)

            # تحديد موقع الإطار الذهبي (مركزه حول الشكل الدائري)
            stroke_x_offset = (template.width - stroke_width) // 2
            stroke_y_offset = y_offset - (stroke_height - new_size[1]) // 2

            # إنشاء طبقة جديدة للإطار الذهبي
            stroke_combined = Image.new("RGBA", template.size, (0, 0, 0, 0))
            stroke_combined.paste(stroke_layer, (stroke_x_offset, stroke_y_offset), stroke_layer)

            # دمج الإطار الذهبي مع الصورة النهائية
            final_image = Image.alpha_composite(template, stroke_combined)

        else:
            # القالب الثاني: صورة بدون دائرة (تأخذ شكل القالب)
            mask = Image.open(TEMPLATE_2_MASK_PATH).convert("L")  # قناع القالب الثاني
            mask = mask.resize((MASK_WIDTH, MASK_HEIGHT), Image.LANCZOS)  # تغيير حجم القناع

            # تغيير حجم الصورة لتناسب حجم القناع
            user_photo = user_photo.resize((MASK_WIDTH, MASK_HEIGHT), Image.LANCZOS)

            # تطبيق القناع على صورة المستخدم (فقط على الشكل الداخلي)
            user_photo.putalpha(mask)

            # تحديد موقع الصورة في القالب
            x_offset = (template.width - MASK_WIDTH) // 2
            y_offset = Y_OFFSET_TEMPLATE_2  # استخدام Y_OFFSET للقالب الثاني

            # إنشاء طبقة جديدة للصورة مع الحفاظ على الإطار الذهبي
            combined_image = Image.new("RGBA", template.size, (0, 0, 0, 0))
            combined_image.paste(user_photo, (x_offset, y_offset), user_photo)

            # دمج الصورة مع القالب (مع الحفاظ على الإطار الذهبي)
            template.paste(combined_image, (0, 0), combined_image)

            # تحميل الإطار الذهبي كطبقة منفصلة
            stroke_layer = Image.open(TEMPLATE_2_STROKE_PATH).convert("RGBA")

            # تغيير حجم الإطار الذهبي بناءً على STROKE_SCALE
            stroke_width = int(MASK_WIDTH * STROKE_SCALE)
            stroke_height = int(MASK_HEIGHT * STROKE_SCALE)
            stroke_layer = stroke_layer.resize((stroke_width, stroke_height), Image.LANCZOS)

            # تحديد موقع الإطار الذهبي (مركزه حول الشكل الداخلي)
            stroke_x_offset = (template.width - stroke_width) // 2
            stroke_y_offset = y_offset - (stroke_height - MASK_HEIGHT) // 2

            # إنشاء طبقة جديدة للإطار الذهبي
            stroke_combined = Image.new("RGBA", template.size, (0, 0, 0, 0))
            stroke_combined.paste(stroke_layer, (stroke_x_offset, stroke_y_offset), stroke_layer)

            # دمج الإطار الذهبي مع الصورة النهائية
            final_image = Image.alpha_composite(template, stroke_combined)

            # تحميل شكل الفنوس كطبقة منفصلة
            fanos_layer = Image.open(FANOS_PATH).convert("RGBA")

            # تغيير حجم شكل الفنوس بناءً على FANOS_WIDTH و FANOS_HEIGHT
            fanos_layer = fanos_layer.resize((FANOS_WIDTH, FANOS_HEIGHT), Image.LANCZOS)

            # تحديد موقع شكل الفنوس (نفس موقع الصورة مع إضافة FANOS_Y_OFFSET)
            fanos_x_offset = (template.width - FANOS_WIDTH) // 2
            fanos_y_offset = y_offset + FANOS_Y_OFFSET

            # إنشاء طبقة جديدة لشكل الفنوس
            fanos_combined = Image.new("RGBA", template.size, (0, 0, 0, 0))
            fanos_combined.paste(fanos_layer, (fanos_x_offset, fanos_y_offset), fanos_layer)

            # دمج شكل الفنوس مع الصورة النهائية
            final_image = Image.alpha_composite(final_image, fanos_combined)

            # إضافة الاسم إذا كان موجودًا
            if user_name:
                draw = ImageDraw.Draw(final_image)
                
                # إعادة تشكيل النص العربي لجعله متصلاً
                reshaped_text = arabic_reshaper.reshape(user_name)
                
                # تطبيق الاتجاه من اليمين إلى اليسار (RTL)
                bidi_text = get_display(reshaped_text)
                
                # تحميل خط يدعم العربية (تأكد من وجود الخط في مسارك)
                font_path = "DG-Bebo-B.ttf"  # استبدل بمسار الخط العربي
                font = ImageFont.truetype(font_path, size=FONT_SIZE)  # استخدام متغير حجم الخط
                
                # حساب أبعاد النص
                text_bbox = draw.textbbox((0, 0), bidi_text, font=font)
                text_width = text_bbox[2] - text_bbox[0]  # عرض النص
                text_height = text_bbox[3] - text_bbox[1]  # ارتفاع النص
                
                # تعديل عرض وارتفاع النص بناءً على المتغيرات
                text_width = int(text_width * FONT_WIDTH)
                text_height = int(text_height * FONT_HEIGHT)
                
                # تحديد موقع النص
                text_x = (final_image.width - text_width) // 2
                text_y = final_image.height + TEXT_Y_OFFSET  # استخدام متغير تحريك النص
                
                # إضافة النص إلى الصورة
                draw.text((text_x, text_y), bidi_text, font=font, fill="white")

        output_path = f"output_{user_id}.png"
        final_image.save(output_path, format="PNG")
        return output_path
    except Exception as e:
        print(f"❌ خطأ أثناء إنشاء البطاقة: {e}")
        import traceback
        traceback.print_exc()  # طباعة تفاصيل الخطأ
        return None

async def handle_photo(update: Update, context: CallbackContext):
    try:
        user_id = update.message.from_user.id
        unique_id = str(uuid.uuid4())[:8]  
        user_photo_path = f"user_photo_{user_id}_{unique_id}.png"

        # انتظار لمدة ثانية قبل الحذف
        await asyncio.sleep(1)
        await update.message.delete()

        # إرسال رسالة "جاري إنشاء التهنئة..."
        processing_msg = await update.message.reply_text("⏳ جارى إنشاء التهنئة، انتظر لحظات...")

        photo_file = await update.message.photo[-1].get_file()
        await photo_file.download_to_drive(user_photo_path)

        # حفظ مسار الصورة في context
        context.user_data['user_photo_path'] = user_photo_path

        # إظهار الأزرار للاختيار بين القوالب
        keyboard = [
            [InlineKeyboardButton("القوالب 1", callback_data='template1')],
            [InlineKeyboardButton("القوالب 2", callback_data='template2')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await processing_msg.edit_text("📂 اختر القالب الذي تريده:", reply_markup=reply_markup)

    except Exception as e:
        print(f"❌ خطأ أثناء معالجة الصورة: {e}")

async def handle_template_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_photo_path = context.user_data.get('user_photo_path')

    if user_photo_path:
        if query.data == 'template2':
            await query.message.reply_text("📝 من فضلك أدخل اسمك:")
            context.user_data['template_choice'] = 'template2'
        else:
            template_path = TEMPLATE_1_PATH
            output_path = create_card(user_photo_path, user_id, template_path)
            if output_path:
                await query.message.reply_photo(photo=open(output_path, 'rb'), caption="🎉 تهنئتك جاهزة! شاركها مع أصدقائك! 🥳")
                os.remove(output_path)
                os.remove(user_photo_path)
            else:
                await query.message.reply_text("❌ حدث خطأ أثناء إنشاء البطاقة. حاول مرة أخرى.")
    else:
        await query.message.reply_text("❌ لم يتم العثور على الصورة. حاول مرة أخرى.")

async def handle_name(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user_photo_path = context.user_data.get('user_photo_path')
    user_name = update.message.text

    if user_photo_path and context.user_data.get('template_choice') == 'template2':
        # إرسال رسالة "جارٍ التصميم"
        processing_msg = await update.message.reply_text("🎨 جارٍ تصميم التهنئة...")

        # حذف رسالة الاسم بعد استلامها
        await asyncio.sleep(1)
        await update.message.delete()

        template_path = TEMPLATE_2_PATH
        output_path = create_card(user_photo_path, user_id, template_path, user_name)
        if output_path:
            await processing_msg.edit_text("✅ تم الانتهاء من التصميم!")
            await asyncio.sleep(1)
            await update.message.reply_photo(photo=open(output_path, 'rb'), caption="🎉 تهنئتك جاهزة! شاركها مع أصدقائك! 🥳")
            os.remove(output_path)
            os.remove(user_photo_path)
        else:
            await processing_msg.edit_text("❌ حدث خطأ أثناء إنشاء البطاقة. حاول مرة أخرى.")
    else:
        await update.message.reply_text("❌ لم يتم العثور على الصورة أو القالب. حاول مرة أخرى.")

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text('🌙 رمضان كريم! أرسل صورتك لإنشاء بطاقة تهنئة.')

def main():
    application = Application.builder().token("7730741199:AAHgGqGOkM4rkRjv4oqpITOnyTUr1JttkmM").build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CallbackQueryHandler(handle_template_choice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name))
    application.run_polling()

if __name__ == '__main__':
    main()