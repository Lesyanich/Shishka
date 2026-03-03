"""
Expenses Shishka Bot — main entry point.
Conversation states use ConversationHandler.
"""
import html
import logging
import os
import traceback
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import config
import sheets
import vision
import drive

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Conversation states ───────────────────────────────────────────────────────
(
    STATE_MAIN,
    STATE_AWAIT_FILE_OR_TEXT,
    STATE_CONFIRM_PARSED,
    STATE_EDIT_FIELD,
    STATE_EDIT_VALUE,
    STATE_AWAIT_DATE,
    STATE_AWAIT_AMOUNT,
    STATE_AWAIT_CURRENCY,
    STATE_AWAIT_SUPPLIER,
    STATE_AWAIT_DETAILS,
    STATE_AWAIT_FLOW_TYPE,
    STATE_AWAIT_CATEGORY,
    STATE_AWAIT_LOCATION,
    STATE_AWAIT_PAID_BY,
    STATE_AWAIT_PAYMENT_METHOD,
    STATE_AWAIT_COMMENT,
    STATE_AWAIT_STATUS,
    STATE_ATTACH_SEARCH,
    STATE_ATTACH_SELECT,
    STATE_ATTACH_DOC_TYPE,
    STATE_ATTACH_FILE,
    STATE_AWAIT_DOC_TYPE_NEW,
    STATE_UPDATE_SEARCH,
    STATE_UPDATE_SELECT,
    STATE_UPDATE_FILE,
    STATE_UPDATE_DOC_TYPE,
    STATE_UPDATE_CONFIRM,
) = range(27)

EDITABLE_FIELDS = {
    "date": "📅 Дата",
    "amount": "💰 Сумма",
    "currency": "💱 Валюта",
    "contractor_name": "🏪 Поставщик",
    "details": "📦 Детали",
    "flow_type": "🏷️ CapEx/OpEx",
    "category_name": "📂 Категория",
    "location": "📍 Локация",
    "paid_by": "👤 Оплатил",
    "payment_method": "💳 Метод оплаты",
    "comment": "💬 Комментарий",
    "status": "✅ Статус",
}

# ── Keyboards ─────────────────────────────────────────────────────────────────

def kb_main():
    return ReplyKeyboardMarkup(
        [
            ["➕ Добавить транзакцию"],
            ["📋 Последние 5", "🔍 Поиск поставщика"],
            ["📎 Прикрепить чек к транзакции"],
            ["🔄 Обновить транзакцию из чека"],
        ],
        resize_keyboard=True,
    )


def kb_doc_type() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏦 Скрин из банка",       callback_data="doctype_bank")],
        [InlineKeyboardButton("🧾 Чек от поставщика",    callback_data="doctype_supplier")],
        [InlineKeyboardButton("📄 Tax Invoice",           callback_data="doctype_tax")],
    ])


def kb_confirm(data: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm")],
        [InlineKeyboardButton("✏️ Исправить", callback_data="edit")],
        [InlineKeyboardButton("❌ Отменить", callback_data="cancel")],
    ])


def kb_edit_fields() -> InlineKeyboardMarkup:
    rows = []
    items = list(EDITABLE_FIELDS.items())
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(items[i][1], callback_data=f"field_{items[i][0]}")]
        if i + 1 < len(items):
            row.append(InlineKeyboardButton(items[i + 1][1], callback_data=f"field_{items[i + 1][0]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 Назад к подтверждению", callback_data="back_confirm")])
    return InlineKeyboardMarkup(rows)


def kb_options(options: list[str], back_cb: str = "back_confirm") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(o, callback_data=f"opt_{o}")] for o in options]
    rows.append([InlineKeyboardButton("🔙 Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


# ── Format helpers ────────────────────────────────────────────────────────────

def e(val) -> str:
    """HTML-escape a value for safe insertion into Telegram HTML messages."""
    return html.escape(str(val)) if val is not None else "—"


def fmt_data(data: dict) -> str:
    lines = [
        f"📅 <b>Дата:</b> {e(data.get('date', '—'))}",
        f"💰 <b>Сумма:</b> {e(data.get('amount', '—'))} {e(data.get('currency', ''))}",
        f"🏪 <b>Поставщик:</b> {e(data.get('contractor_name') or data.get('supplier_name') or '—')}",
        f"📦 <b>Детали:</b> {e(data.get('details', '—'))}",
        f"🏷 <b>Тип:</b> {e(data.get('flow_type', '—'))}",
        f"📂 <b>Категория:</b> {e(data.get('category_name', '—'))}",
        f"📍 <b>Локация:</b> {e(data.get('location', '—'))}",
        f"👤 <b>Оплатил:</b> {e(data.get('paid_by', '—'))}",
        f"💳 <b>Метод оплаты:</b> {e(data.get('payment_method', '—'))}",
        f"✅ <b>Статус:</b> {e(data.get('status', 'paid'))}",
    ]
    if data.get("comment"):
        lines.append(f"💬 <b>Комментарий:</b> {e(data['comment'])}")
    return "\n".join(lines)


def today_str() -> str:
    return datetime.now().strftime("%d.%m.%Y")


# ── Handlers ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    log.info(f"START from chat_id={update.effective_chat.id}, user={update.effective_user.username}")
    await update.message.reply_text(
        "👋 Привет! Я бот для учёта расходов <b>Shishka</b>.\n\n"
        "Отправь фото чека, скрин из банка или Tax Invoice — "
        "я распознаю данные автоматически.\n\n"
        "Или нажми кнопку ниже для ручного ввода.",
        parse_mode="HTML",
        reply_markup=kb_main(),
    )
    return STATE_MAIN


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("Отменено.", reply_markup=kb_main())
    return STATE_MAIN


async def handle_main_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "➕ Добавить транзакцию":
        await update.message.reply_text(
            "📎 Отправь фото чека/скрина из банка/Tax Invoice, "
            "или напиши данные текстом.\n\n"
            "Пример: <code>5000 THB, Makro, vegetables, L2 Tops, Lesya</code>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return STATE_AWAIT_FILE_OR_TEXT

    if text == "📋 Последние 5":
        await show_recent(update, ctx)
        return STATE_MAIN

    if text == "🔍 Поиск поставщика":
        await update.message.reply_text("Введи имя или ID поставщика:")
        return STATE_MAIN

    if text == "📎 Прикрепить чек к транзакции":
        await update.message.reply_text(
            "Введи ID транзакции (например <code>20260301001</code>) "
            "или часть описания для поиска:",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return STATE_ATTACH_SEARCH

    if text == "🔄 Обновить транзакцию из чека":
        await update.message.reply_text(
            "Отправь фото или документ чека — я сам найду транзакцию и дополню данные.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return STATE_UPDATE_FILE

    return STATE_MAIN


async def show_recent(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        rows = sheets._read(f"{config.SHEET_EXPENSES}!A2:V500")
        last5 = rows[-5:] if len(rows) >= 5 else rows
        lines = []
        for r in reversed(last5):
            tid = r[0] if len(r) > 0 else "?"
            dt = r[1] if len(r) > 1 else "?"
            amt = r[10] if len(r) > 10 else "?"
            cur = r[11] if len(r) > 11 else ""
            det = r[9] if len(r) > 9 else "?"
            lines.append(f"• <code>{html.escape(tid)}</code> {html.escape(dt)} — {html.escape(amt)} {html.escape(cur)} — {html.escape(det)}")
        text = "📋 <b>Последние транзакции:</b>\n" + "\n".join(lines)
    except Exception as ex:
        text = f"Ошибка загрузки: {html.escape(str(ex))}"
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb_main())


# ── Receipt / text input ──────────────────────────────────────────────────────

async def handle_file_or_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Receives photo, document, or text — extracts data.
    If file, first ask doc type (unless already set from callback)."""
    msg = update.message

    # If this is a file and doc_type not yet set, download & save, then ask doc type
    if (msg.photo or msg.document) and not ctx.user_data.get("doc_type"):
        try:
            if msg.photo:
                photo = msg.photo[-1]
                tg_file = await photo.get_file()
                raw = await tg_file.download_as_bytearray()
                ctx.user_data["pending_file_bytes"] = bytes(raw)
                ctx.user_data["pending_mime_type"] = "image/jpeg"
                ctx.user_data["pending_filename"] = f"{photo.file_id}.jpg"
            else:
                doc = msg.document
                tg_file = await doc.get_file()
                raw = await tg_file.download_as_bytearray()
                ctx.user_data["pending_file_bytes"] = bytes(raw)
                ctx.user_data["pending_mime_type"] = doc.mime_type or "application/octet-stream"
                ctx.user_data["pending_filename"] = doc.file_name or f"{doc.file_id}"
        except Exception as fetch_err:
            await msg.reply_text(f"❌ Ошибка загрузки файла: {fetch_err}")
            return STATE_AWAIT_FILE_OR_TEXT
        await msg.reply_text(
            "Что это за документ?",
            reply_markup=kb_doc_type(),
        )
        return STATE_AWAIT_DOC_TYPE_NEW

    processing_msg = await msg.reply_text("⏳ Обрабатываю...")

    parsed = {}
    file_bytes = None
    mime_type = "image/jpeg"
    original_filename = None

    try:
        if msg.photo:
            photo = msg.photo[-1]
            file = await photo.get_file()
            file_bytes = await file.download_as_bytearray()
            mime_type = "image/jpeg"
            original_filename = f"{photo.file_id}.jpg"
            parsed = vision.parse_receipt(bytes(file_bytes), mime_type)

        elif msg.document:
            doc = msg.document
            mime_type = doc.mime_type or "application/octet-stream"
            original_filename = doc.file_name or f"{doc.file_id}"
            file = await doc.get_file()
            file_bytes = await file.download_as_bytearray()
            if "image" in mime_type or "pdf" in mime_type:
                parsed = vision.parse_receipt(bytes(file_bytes), mime_type)
            else:
                parsed = {}

        elif msg.text:
            if msg.text.startswith("/"):
                return STATE_MAIN
            parsed = vision.parse_text(msg.text)

        else:
            await processing_msg.edit_text("Поддерживаются фото, документы и текст.")
            return STATE_AWAIT_FILE_OR_TEXT

    except Exception as e:
        log.error(traceback.format_exc())
        await processing_msg.edit_text(f"Ошибка парсинга: {e}\nВведи данные вручную.")
        parsed = {}

    # Defaults
    if not parsed.get("date"):
        parsed["date"] = today_str()
    if not parsed.get("currency"):
        parsed["currency"] = "THB"
    if not parsed.get("status"):
        parsed["status"] = "paid"

    # Normalize contractor_name
    if "supplier_name" in parsed and not parsed.get("contractor_name"):
        parsed["contractor_name"] = parsed.pop("supplier_name")

    # Store in context
    ctx.user_data["expense"] = parsed
    ctx.user_data["file_bytes"] = file_bytes
    ctx.user_data["mime_type"] = mime_type
    ctx.user_data["original_filename"] = original_filename

    await processing_msg.delete()
    await ask_confirmation(update, ctx, parsed)
    return STATE_CONFIRM_PARSED


async def ask_confirmation(update: Update, ctx: ContextTypes.DEFAULT_TYPE, data: dict):
    text = "📋 <b>Проверь данные:</b>\n\n" + fmt_data(data) + "\n\nВсё верно?"
    await update.message.reply_text(
        text, parse_mode="HTML", reply_markup=kb_confirm(data)
    )


# ── Confirmation callbacks ────────────────────────────────────────────────────

async def cb_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = ctx.user_data.get("expense", {})

    log.info(f"[CONFIRM] expense keys={list(data.keys())}, "
             f"payment_method={data.get('payment_method')!r}, "
             f"all_user_data_keys={list(ctx.user_data.keys())}")

    # Check required fields
    missing = []
    for field in ("date", "amount", "currency", "details", "location", "paid_by", "payment_method"):
        if not data.get(field):
            missing.append(EDITABLE_FIELDS.get(field, field))

    if missing:
        log.info(f"[CONFIRM] missing fields: {missing}")
        await query.edit_message_text(
            f"⚠️ Заполни обязательные поля: {html.escape(', '.join(missing))}\n\n"
            + fmt_data(data),
            parse_mode="HTML",
            reply_markup=kb_edit_fields(),
        )
        return STATE_EDIT_FIELD

    # Upload receipt to the correct Drive folder
    link_supplier = ""
    link_bank = ""
    file_bytes = ctx.user_data.get("file_bytes")
    doc_type = ctx.user_data.get("doc_type", "bank")  # bank | supplier | tax
    if file_bytes:
        try:
            filename = ctx.user_data.get("original_filename") or "receipt.jpg"
            mime = ctx.user_data.get("mime_type", "image/jpeg")
            url = drive.upload_file(bytes(file_bytes), filename, mime, doc_type=doc_type)
            if doc_type == "supplier" or doc_type == "tax":
                link_supplier = url
            else:
                link_bank = url
        except Exception as upload_err:
            log.warning(f"Drive upload failed: {upload_err}")

    # Map supplier — or auto-add if new
    try:
        sups = sheets.get_suppliers()
        contractor_name = (data.get("contractor_name") or "").strip()
        if contractor_name:
            matched = next(
                (s for s in sups if contractor_name.lower() in s["name"].lower()
                 or s["name"].lower() in contractor_name.lower()),
                None,
            )
            if matched:
                data["contractor_id"] = matched["id"]
                data["contractor_name"] = matched["name"]
            else:
                # New contractor — add to REF_Suppliers automatically
                new_id = sheets.add_supplier(contractor_name)
                data["contractor_id"] = new_id
                log.info(f"New supplier added: {new_id} — {contractor_name}")
    except Exception:
        pass

    # Map category
    try:
        cats = sheets.get_categories()
        cat_name = data.get("category_name", "")
        matched_cat = next(
            (c for c in cats if cat_name.lower() in c["name"].lower()),
            None,
        )
        if matched_cat:
            data["category_id"] = matched_cat["code"]
    except Exception:
        pass

    data["link_bank"] = link_bank
    data["link_supplier"] = link_supplier
    data["input_source"] = config.INPUT_SOURCE

    try:
        tx_id = sheets.append_expense(data)
        await query.edit_message_text(
            f"✅ <b>Записано!</b>\n\n"
            f"ID: <code>{html.escape(tx_id)}</code>\n"
            f"📅 {e(data.get('date'))} · {e(data.get('amount'))} {e(data.get('currency'))}\n"
            f"📦 {e(data.get('details'))}\n"
            f"📍 {e(data.get('location'))} · 👤 {e(data.get('paid_by'))}",
            parse_mode="HTML",
        )
    except Exception as err:
        log.error(traceback.format_exc())
        await query.edit_message_text(f"❌ Ошибка записи: {html.escape(str(err))}")

    ctx.user_data.clear()
    await query.message.reply_text("Готово! Что дальше?", reply_markup=kb_main())
    return STATE_MAIN


async def cb_edit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = ctx.user_data.get("expense", {})
    await query.edit_message_text(
        "✏️ Выбери поле для редактирования:\n\n" + fmt_data(data),
        parse_mode="HTML",
        reply_markup=kb_edit_fields(),
    )
    return STATE_EDIT_FIELD


async def cb_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data.clear()
    await query.edit_message_text("❌ Отменено.")
    await query.message.reply_text("Главное меню:", reply_markup=kb_main())
    return STATE_MAIN


async def cb_back_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    log.info(f"[BACK_CONFIRM] returning to confirm screen")
    data = ctx.user_data.get("expense", {})
    await query.edit_message_text(
        "📋 <b>Проверь данные:</b>\n\n" + fmt_data(data) + "\n\nВсё верно?",
        parse_mode="HTML",
        reply_markup=kb_confirm(data),
    )
    return STATE_CONFIRM_PARSED


# ── Field editing ─────────────────────────────────────────────────────────────

FIELD_PROMPTS = {
    "date":           ("Введи дату (DD.MM.YYYY):", None),
    "amount":         ("Введи сумму (число):", None),
    "currency":       ("Выбери валюту:", config.CURRENCIES),
    "contractor_name":("Введи название поставщика:", None),
    "details":        ("Введи детали (что куплено):", None),
    "flow_type":      ("Выбери тип:", config.FLOW_TYPES),
    "category_name":  ("Выбери категорию:", ["Equipment", "Construction", "Furniture",
                                              "Decoration", "IT Software", "Legal",
                                              "Rent", "Water/electricity bills"]),
    "location":       ("Выбери локацию:", config.LOCATIONS),
    "paid_by":        ("Кто оплатил?", config.PAID_BY),
    "payment_method": ("Способ оплаты:", config.PAYMENT_METHODS),
    "comment":        ("Введи комментарий:", None),
    "status":         ("Статус оплаты:", config.STATUSES),
}


async def cb_field_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.replace("field_", "")
    ctx.user_data["editing_field"] = field
    log.info(f"[FIELD] selected field={field!r}, callback_data={query.data!r}")

    prompt, options = FIELD_PROMPTS.get(field, ("Введи значение:", None))
    if options:
        await query.edit_message_text(
            prompt, reply_markup=kb_options(options)
        )
    else:
        await query.edit_message_text(prompt)
    return STATE_EDIT_VALUE


async def cb_option_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    value = query.data.replace("opt_", "")
    field = ctx.user_data.get("editing_field")

    log.info(f"[OPTION] field={field!r}, value={value!r}")

    if field:
        if "expense" not in ctx.user_data:
            ctx.user_data["expense"] = {}
        ctx.user_data["expense"][field] = value
        log.info(f"[OPTION] Saved expense[{field}]={value!r}")

    data = ctx.user_data.get("expense", {})
    await query.edit_message_text(
        "📋 <b>Проверь данные:</b>\n\n" + fmt_data(data) + "\n\nВсё верно?",
        parse_mode="HTML",
        reply_markup=kb_confirm(data),
    )
    return STATE_CONFIRM_PARSED


async def handle_edit_value(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Free-text input for a field being edited."""
    field = ctx.user_data.get("editing_field")
    value = update.message.text.strip()

    if field == "amount":
        try:
            value = float(value.replace(",", "").replace(" ", ""))
        except ValueError:
            await update.message.reply_text("Введи число, например: 5000")
            return STATE_EDIT_VALUE

    if field:
        ctx.user_data["expense"][field] = value

    data = ctx.user_data.get("expense", {})
    await update.message.reply_text(
        "📋 <b>Проверь данные:</b>\n\n" + fmt_data(data) + "\n\nВсё верно?",
        parse_mode="HTML",
        reply_markup=kb_confirm(data),
    )
    return STATE_CONFIRM_PARSED


# ── Doc type selection for new transaction ───────────────────────────────────

async def cb_doc_type_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """User selected doc type for a new transaction — process the already-saved file."""
    query = update.callback_query
    await query.answer()
    doc_type = query.data.replace("doctype_", "")
    ctx.user_data["doc_type"] = doc_type

    file_bytes = ctx.user_data.pop("pending_file_bytes", None)
    mime_type = ctx.user_data.pop("pending_mime_type", "image/jpeg")
    original_filename = ctx.user_data.pop("pending_filename", "receipt")

    if not file_bytes:
        # Fallback: no saved bytes (shouldn't happen), ask to resend
        await query.edit_message_text("⏳ Пришли файл ещё раз — или напиши данные текстом.")
        return STATE_AWAIT_FILE_OR_TEXT

    await query.edit_message_text("⏳ Обрабатываю...")

    parsed = {}
    try:
        if "image" in mime_type or "pdf" in mime_type:
            parsed = vision.parse_receipt(file_bytes, mime_type)
    except Exception as err:
        log.error(traceback.format_exc())
        parsed = {}

    # Defaults
    if not parsed.get("date"):
        parsed["date"] = today_str()
    if not parsed.get("currency"):
        parsed["currency"] = "THB"
    if not parsed.get("status"):
        parsed["status"] = "paid"
    if "supplier_name" in parsed and not parsed.get("contractor_name"):
        parsed["contractor_name"] = parsed.pop("supplier_name")

    ctx.user_data["expense"] = parsed
    ctx.user_data["file_bytes"] = file_bytes
    ctx.user_data["mime_type"] = mime_type
    ctx.user_data["original_filename"] = original_filename

    await query.edit_message_text(
        "📋 <b>Проверь данные:</b>\n\n" + fmt_data(parsed) + "\n\nВсё верно?",
        parse_mode="HTML",
        reply_markup=kb_confirm(parsed),
    )
    return STATE_CONFIRM_PARSED


# ── Attach file to existing transaction ──────────────────────────────────────

async def handle_attach_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """User typed a transaction ID or description to search."""
    query_text = update.message.text.strip()
    rows = sheets._read(f"{config.SHEET_EXPENSES}!A2:V500")

    matches = []
    for i, r in enumerate(rows):
        if not r or not any(r):
            continue
        row_str = " ".join(str(c) for c in r).lower()
        if query_text.lower() in row_str:
            matches.append((i + 2, r))  # (sheet_row, data)

    if not matches:
        await update.message.reply_text(
            "Транзакция не найдена. Попробуй ещё раз или /cancel.",
            reply_markup=kb_main(),
        )
        return STATE_MAIN

    if len(matches) == 1:
        sheet_row, r = matches[0]
        ctx.user_data["attach_row"] = sheet_row
        ctx.user_data["attach_tx"] = r
        return await _ask_doc_type(update, ctx, sheet_row, r)

    # Multiple matches — show list
    kb_rows = []
    for sheet_row, r in matches[:8]:
        tx_id = r[0] if r else "?"
        dt = r[1] if len(r) > 1 else ""
        amt = r[10] if len(r) > 10 else ""
        cur = r[11] if len(r) > 11 else ""
        det = r[9] if len(r) > 9 else ""
        label = f"{tx_id} | {dt} | {amt} {cur} | {det}"[:60]
        kb_rows.append([InlineKeyboardButton(label, callback_data=f"attach_{sheet_row}")])

    await update.message.reply_text(
        f"Найдено {len(matches)} транзакций. Выбери нужную:",
        reply_markup=InlineKeyboardMarkup(kb_rows),
    )
    ctx.user_data["attach_matches"] = {sr: r for sr, r in matches[:8]}
    return STATE_ATTACH_SELECT


async def _ask_doc_type(update, ctx, sheet_row, r):
    tx_id = r[0] if r else "?"
    dt = r[1] if len(r) > 1 else ""
    amt = r[10] if len(r) > 10 else ""
    cur = r[11] if len(r) > 11 else ""
    await update.message.reply_text(
        f"Транзакция: <code>{html.escape(tx_id)}</code> · {html.escape(dt)} · {html.escape(amt)} {html.escape(cur)}\n\n"
        "Какой тип документа прикрепляешь?",
        parse_mode="HTML",
        reply_markup=kb_doc_type(),
    )
    return STATE_ATTACH_DOC_TYPE


async def cb_attach_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sheet_row = int(query.data.replace("attach_", ""))
    matches = ctx.user_data.get("attach_matches", {})
    r = matches.get(sheet_row, [])
    ctx.user_data["attach_row"] = sheet_row
    ctx.user_data["attach_tx"] = r

    tx_id = r[0] if r else "?"
    dt = r[1] if len(r) > 1 else ""
    amt = r[10] if len(r) > 10 else ""
    cur = r[11] if len(r) > 11 else ""
    await query.edit_message_text(
        f"Транзакция: <code>{html.escape(tx_id)}</code> · {html.escape(dt)} · {html.escape(amt)} {html.escape(cur)}\n\n"
        "Какой тип документа прикрепляешь?",
        parse_mode="HTML",
        reply_markup=kb_doc_type(),
    )
    return STATE_ATTACH_DOC_TYPE


async def cb_attach_doc_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    doc_type = query.data.replace("doctype_", "")  # bank | supplier | tax
    ctx.user_data["attach_doc_type"] = doc_type

    labels = {"bank": "скрин из банка", "supplier": "чек от поставщика", "tax": "Tax Invoice"}
    await query.edit_message_text(
        f"Тип: <b>{labels.get(doc_type, doc_type)}</b>\n\nОтправь файл (фото или документ):",
        parse_mode="HTML",
    )
    return STATE_ATTACH_FILE


async def handle_attach_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Receives the file to attach to a transaction."""
    msg = update.message
    processing = await msg.reply_text("⏳ Загружаю файл...")

    file_bytes = None
    mime_type = "image/jpeg"
    filename = "receipt.jpg"

    try:
        if msg.photo:
            photo = msg.photo[-1]
            file = await photo.get_file()
            file_bytes = bytes(await file.download_as_bytearray())
            filename = f"{photo.file_id}.jpg"
        elif msg.document:
            doc = msg.document
            file = await doc.get_file()
            file_bytes = bytes(await file.download_as_bytearray())
            mime_type = doc.mime_type or "application/octet-stream"
            filename = doc.file_name or f"{doc.file_id}"
        else:
            await processing.edit_text("Пришли фото или файл.")
            return STATE_ATTACH_FILE
    except Exception as fetch_err:
        await processing.edit_text(f"Ошибка загрузки файла: {fetch_err}")
        return STATE_ATTACH_FILE

    doc_type = ctx.user_data.get("attach_doc_type", "bank")
    sheet_row = ctx.user_data.get("attach_row")
    r = ctx.user_data.get("attach_tx", [])
    tx_id = r[0] if r else "?"

    # Upload to Drive
    try:
        url = drive.upload_file(file_bytes, filename, mime_type, doc_type=doc_type)
    except Exception as up_err:
        await processing.edit_text(
            f"⚠️ Файл не удалось загрузить в Drive: {up_err}\n"
            "Проверь доступ к папке (поделись с сервисным аккаунтом)."
        )
        ctx.user_data.clear()
        await msg.reply_text("Главное меню:", reply_markup=kb_main())
        return STATE_MAIN

    # Write link to the correct column (U=supplier, V=bank)
    if sheet_row and url:
        col = "U" if doc_type in ("supplier", "tax") else "V"
        existing = sheets._read(f"{config.SHEET_EXPENSES}!{col}{sheet_row}:{col}{sheet_row}")
        existing_val = existing[0][0] if existing and existing[0] else ""
        # Append to existing links (space-separated)
        new_val = f"{existing_val} {url}".strip() if existing_val else url
        sheets._get_service().spreadsheets().values().update(
            spreadsheetId=config.SPREADSHEET_ID,
            range=f"{config.SHEET_EXPENSES}!{col}{sheet_row}",
            valueInputOption="USER_ENTERED",
            body={"values": [[new_val]]},
        ).execute()

    await processing.delete()
    await msg.reply_text(
        f"✅ Файл прикреплён к транзакции <code>{html.escape(tx_id)}</code>!\n"
        f"🔗 <a href='{url}'>Открыть в Drive</a>",
        parse_mode="HTML",
        reply_markup=kb_main(),
    )
    ctx.user_data.clear()
    return STATE_MAIN


def _cell_missing(val) -> bool:
    """True if a cell is empty OR contains a formula error (#N/A, #REF!, etc.)."""
    if not val:
        return True
    return str(val).strip().startswith("#")


def _fmt_missing_fields(r: list) -> str:
    """Return a human-readable list of empty/error fields for the update flow."""
    FIELDS = [
        (8,  "🏪 Поставщик"),
        (5,  "🆔 Поставщик ID"),
        (2,  "🏷 Тип"),
        (4,  "📂 Категория"),
        (9,  "📦 Детали"),
        (12, "💬 Комментарий"),
        (20, "🔗 Чек/Invoice"),
    ]
    def _c(row, idx):
        return row[idx] if len(row) > idx else ""
    missing = [lbl for idx, lbl in FIELDS if _cell_missing(_c(r, idx))]
    if not missing:
        return ""
    return "⚠️ <b>Не заполнено:</b> " + ", ".join(missing)


async def _warn_send_text_first(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Remind user to send transaction ID as text when they send a photo too early."""
    await update.message.reply_text(
        "⚠️ Сначала введи ID транзакции текстом (например: <code>20260112001</code>)\n"
        "или напиши часть описания — я найду транзакцию по поиску.",
        parse_mode="HTML",
    )


# ── Update existing transaction from receipt ──────────────────────────────────

def kb_doc_type_update() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏦 Скрин из банка",     callback_data="updtype_bank")],
        [InlineKeyboardButton("🧾 Чек от поставщика",  callback_data="updtype_supplier")],
        [InlineKeyboardButton("📄 Tax Invoice",         callback_data="updtype_tax")],
    ])


def _search_expense_rows(query_text: str) -> list:
    """Text search — used as fallback when auto-match fails."""
    rows = sheets._read(f"{config.SHEET_EXPENSES}!A2:V500")
    matches = []
    for i, r in enumerate(rows):
        if not r or not any(r):
            continue
        if query_text.lower() in " ".join(str(c) for c in r).lower():
            matches.append((i + 2, r))
    return matches


def _find_matching_transactions(parsed: dict) -> list:
    """
    Auto-search: find transactions matching a parsed receipt by date + amount.
    Returns list of (sheet_row, row_data) sorted by relevance, up to 8.
    """
    rows = sheets._read(f"{config.SHEET_EXPENSES}!A2:V500")

    parsed_date = (parsed.get("date") or "").strip()       # DD.MM.YYYY
    parsed_amount = parsed.get("amount")
    parsed_supplier = (
        parsed.get("contractor_name") or parsed.get("supplier_name") or ""
    ).lower()

    scored = []
    for i, r in enumerate(rows):
        if not r or not any(r):
            continue
        row_date = r[1] if len(r) > 1 else ""
        row_amount_raw = r[10] if len(r) > 10 else ""
        row_supplier = (r[8] if len(r) > 8 else "").lower()

        score = 0

        # Date match (exact) — primary criterion
        if parsed_date and row_date == parsed_date:
            score += 4

        # Amount match ±5%
        if parsed_amount:
            try:
                row_amt = float(
                    str(row_amount_raw)
                    .replace(",", ".").replace("\xa0", "").replace(" ", "")
                )
                diff_pct = abs(row_amt - float(parsed_amount)) / max(float(parsed_amount), 1)
                if diff_pct <= 0.05:
                    score += 3
                elif diff_pct <= 0.20:
                    score += 1
            except (ValueError, TypeError):
                pass

        # Supplier partial match
        if parsed_supplier and row_supplier:
            words = [w for w in parsed_supplier.split() if len(w) >= 3]
            if any(w in row_supplier for w in words):
                score += 2

        if score >= 4:   # date must match
            scored.append((i + 2, r, score))

    scored.sort(key=lambda x: -x[2])
    return [(sr, r) for sr, r, _ in scored[:8]]


def _compute_update_proposed(parsed: dict, drive_url: str, doc_type: str, row: list):
    """
    Compute proposed cell updates for a transaction row.
    Returns (proposed_dict, changes_map).
    - proposed_dict: {col: (label, value)} — all columns to write
    - changes_map:   {col: html_text}      — user-visible changes (col F is silent, not included)
    - Other fields (type, category, details, comment): fill only if empty/error.
    - Supplier (name + id): always update if receipt has one and value differs.
    - Drive link: always add.
    """
    def _cell(r, idx):
        return r[idx] if len(r) > idx else ""

    # ── Resolve supplier from receipt ─────────────────────────────────────────
    contractor_name_raw = (parsed.get("contractor_name") or "").strip()
    resolved_name = contractor_name_raw
    resolved_id = ""

    if contractor_name_raw:
        try:
            sups = sheets.get_suppliers()
            matched = next(
                (s for s in sups
                 if s.get("name")  # skip empty-name rows (empty string matches everything)
                 and (contractor_name_raw.lower() in s["name"].lower()
                      or s["name"].lower() in contractor_name_raw.lower())),
                None,
            )
            if matched and matched.get("name"):
                resolved_id = matched["id"]
                resolved_name = matched["name"]
                log.info(f"[UPDATE] Supplier matched: {resolved_id} — {resolved_name}")
            else:
                resolved_id = sheets.add_supplier(contractor_name_raw)
                resolved_name = contractor_name_raw
                log.info(f"[UPDATE] New supplier added: {resolved_id} — {contractor_name_raw}")
        except Exception:
            log.error(f"[UPDATE] Supplier resolve failed: {traceback.format_exc()}")

    # ── Other fields ───────────────────────────────────────────────────────────
    # Fill-if-empty: only write when the cell is blank/error
    FILL_IF_EMPTY = [
        ("flow_type",     2,  "C", "🏷 Тип"),
        ("category_name", 4,  "E", "📂 Категория"),
    ]
    # Always-propose: show current→new and let user toggle (like supplier)
    ALWAYS_PROPOSE = [
        ("details",  9,  "J", "📦 Детали"),
        ("comment", 12,  "M", "💬 Комментарий"),
    ]

    proposed = {}
    changes_map = {}  # col → HTML display text (user-visible; col F is silent)

    for field, idx, col, label in FILL_IF_EMPTY:
        current = _cell(row, idx)
        new_val = parsed.get(field)
        if _cell_missing(current) and new_val:
            proposed[col] = (label, new_val)
            changes_map[col] = f"{label}: — → <b>{e(new_val)}</b>"

    for field, idx, col, label in ALWAYS_PROPOSE:
        current = _cell(row, idx)
        new_val = (parsed.get(field) or "").strip()
        if not new_val:
            continue
        if _cell_missing(current):
            proposed[col] = (label, new_val)
            changes_map[col] = f"{label}: — → <b>{e(new_val)}</b>"
        elif current.strip() != new_val:
            proposed[col] = (label, new_val)
            cur_short = current.strip()[:40] + ("…" if len(current.strip()) > 40 else "")
            changes_map[col] = f"{label}: {e(cur_short)} → <b>{e(new_val)}</b>"

    # ── Supplier: always update if parsed name differs from current ────────────
    log.info(f"[UPDATE] resolved_name={resolved_name!r}, resolved_id={resolved_id!r}, "
             f"current_name={_cell(row, 8)!r}, current_id={_cell(row, 5)!r}")
    if resolved_name:
        current_name = _cell(row, 8)   # col I
        current_id   = _cell(row, 5)   # col F

        name_missing  = _cell_missing(current_name)
        name_differs  = (not name_missing
                         and current_name.strip().lower() != resolved_name.lower())

        if name_missing:
            proposed["I"] = ("🏪 Поставщик", resolved_name)
            changes_map["I"] = f"🏪 Поставщик: — → <b>{e(resolved_name)}</b>"
        elif name_differs:
            proposed["I"] = ("🏪 Поставщик", resolved_name)
            changes_map["I"] = (
                f"🏪 Поставщик: {e(current_name)} → <b>{e(resolved_name)}</b>"
            )

        if resolved_id and (_cell_missing(current_id) or current_id != resolved_id):
            proposed["F"] = ("🆔 ID поставщика", resolved_id)
            # col F is silent — no entry in changes_map

    # ── Amount: always propose if parsed value differs from current ────────────
    amount_new = parsed.get("amount")
    currency_new = (parsed.get("currency") or "THB").strip()
    if amount_new is not None:
        current_amt_str = _cell(row, 10)   # col K
        try:
            current_amt = float(str(current_amt_str).replace(",", "").strip())
        except (ValueError, TypeError):
            current_amt = None
        amt_missing = current_amt is None or _cell_missing(current_amt_str)
        amt_differs = (not amt_missing) and abs(current_amt - float(amount_new)) > 0.01
        if amt_missing:
            proposed["K"] = ("💰 Сумма", amount_new)
            changes_map["K"] = f"💰 Сумма: — → <b>{amount_new} {e(currency_new)}</b>"
        elif amt_differs:
            proposed["K"] = ("💰 Сумма", amount_new)
            changes_map["K"] = (
                f"💰 Сумма: {e(current_amt_str)} → <b>{amount_new} {e(currency_new)}</b>"
            )
        # Currency — silent, paired with amount
        current_cur = _cell(row, 11)   # col L
        if amount_new is not None and "K" in proposed:
            if _cell_missing(current_cur) or current_cur != currency_new:
                proposed["L"] = ("Валюта", currency_new)

    # ── Drive link ─────────────────────────────────────────────────────────────
    if drive_url:
        col_link   = "U" if doc_type in ("supplier", "tax") else "V"
        label_link = "🔗 Tax Invoice / чек" if doc_type != "bank" else "🔗 Скрин банка"
        proposed[col_link] = (label_link, drive_url)
        changes_map[col_link] = f"{label_link}: загружен в Drive"

    log.info(f"[UPDATE] proposed keys={list(proposed.keys())}, changes_map keys={list(changes_map.keys())}")
    return proposed, changes_map


def _strip_html(text: str) -> str:
    """Remove HTML tags for use in button labels."""
    return text.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")


def _build_update_keyboard(proposed: dict, changes_map: dict, selected: set) -> InlineKeyboardMarkup:
    """Build toggle keyboard: short label per change row + Apply / Cancel."""
    rows = []
    for col in changes_map:
        check = "✅" if col in selected else "◻️"
        short = proposed[col][0] if col in proposed else col   # e.g. "📦 Детали"
        rows.append([InlineKeyboardButton(f"{check}  {short}", callback_data=f"updtoggle_{col}")])
    n = len(selected)
    apply_label = (
        f"💾 Применить выбранное ({n})" if n > 0 else "— ничего не выбрано —"
    )
    rows.append([InlineKeyboardButton(apply_label, callback_data="updconfirm")])
    rows.append([InlineKeyboardButton("❌ Отменить", callback_data="updcancel")])
    return InlineKeyboardMarkup(rows)


async def _show_update_confirm(edit_fn, reply_fn, ctx, proposed, changes_map, tx_id):
    """Render the toggle-selection confirmation message for an update."""
    ctx.user_data["update_proposed"]   = proposed
    ctx.user_data["update_changes_map"] = changes_map
    ctx.user_data["update_tx_id"]      = tx_id
    # Initially all user-visible changes are selected
    ctx.user_data["update_selected"]   = set(changes_map.keys())

    if not proposed:
        await edit_fn(
            f"ℹ️ Транзакция <code>{html.escape(tx_id)}</code> уже полностью заполнена.",
            parse_mode="HTML",
        )
        await reply_fn("Главное меню:", reply_markup=kb_main())
        ctx.user_data.clear()
        return STATE_MAIN

    # Full change details in message text; short labels in buttons
    details_lines = "\n".join(f"• {text}" for text in changes_map.values())
    keyboard = _build_update_keyboard(proposed, changes_map, ctx.user_data["update_selected"])
    await edit_fn(
        f"📝 <b>Изменения для <code>{html.escape(tx_id)}</code>:</b>\n\n"
        + details_lines
        + "\n\nНажми кнопку чтобы включить/отключить:",
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    return STATE_UPDATE_CONFIRM


async def cb_update_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Toggle a single proposed change on/off and re-render the keyboard."""
    query = update.callback_query
    await query.answer()
    col = query.data.replace("updtoggle_", "")

    selected = ctx.user_data.get("update_selected", set())
    if col in selected:
        selected.discard(col)
    else:
        selected.add(col)
    ctx.user_data["update_selected"] = selected

    proposed    = ctx.user_data.get("update_proposed", {})
    changes_map = ctx.user_data.get("update_changes_map", {})
    keyboard = _build_update_keyboard(proposed, changes_map, selected)
    try:
        await query.edit_message_reply_markup(reply_markup=keyboard)
    except Exception:
        pass
    return STATE_UPDATE_CONFIRM


async def cb_update_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """User picks a transaction from the auto-matched list."""
    query = update.callback_query
    await query.answer()
    sheet_row = int(query.data.replace("updsel_", ""))
    matches = ctx.user_data.get("update_matches", {})
    row = matches.get(sheet_row, [])
    ctx.user_data["update_row"] = sheet_row
    ctx.user_data["update_tx_row"] = row
    ctx.user_data["update_sheet_row"] = sheet_row

    parsed = ctx.user_data.get("update_parsed", {})
    drive_url = ctx.user_data.get("update_drive_url", "")
    doc_type = ctx.user_data.get("update_doc_type", "supplier")

    proposed, changes_text = _compute_update_proposed(parsed, drive_url, doc_type, row)
    tx_id = row[0] if row else "?"
    return await _show_update_confirm(
        lambda t, **kw: query.edit_message_text(t, **kw),
        lambda t, **kw: query.message.reply_text(t, **kw),
        ctx, proposed, changes_text, tx_id,
    )


async def handle_update_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Fallback: user types transaction ID / description when auto-search failed."""
    query_text = update.message.text.strip()
    matches = _search_expense_rows(query_text)

    if not matches:
        await update.message.reply_text(
            "Транзакция не найдена. Попробуй другой ID или /cancel.",
        )
        return STATE_UPDATE_SEARCH

    parsed = ctx.user_data.get("update_parsed", {})
    drive_url = ctx.user_data.get("update_drive_url", "")
    doc_type = ctx.user_data.get("update_doc_type", "supplier")

    if len(matches) == 1:
        sheet_row, row = matches[0]
        ctx.user_data["update_sheet_row"] = sheet_row
        ctx.user_data["update_tx_row"] = row
        proposed, changes_text = _compute_update_proposed(parsed, drive_url, doc_type, row)
        tx_id = row[0] if row else "?"
        sent = await update.message.reply_text("…")
        return await _show_update_confirm(
            lambda t, **kw: sent.edit_text(t, **kw),
            lambda t, **kw: update.message.reply_text(t, **kw),
            ctx, proposed, changes_text, tx_id,
        )

    kb_rows = []
    for sheet_row, r in matches[:8]:
        tx_id = r[0] if r else "?"
        dt = r[1] if len(r) > 1 else ""
        amt = r[10] if len(r) > 10 else ""
        cur = r[11] if len(r) > 11 else ""
        label = f"{tx_id} | {dt} | {amt} {cur}"[:60]
        kb_rows.append([InlineKeyboardButton(label, callback_data=f"updsel_{sheet_row}")])

    ctx.user_data["update_matches"] = {sr: r for sr, r in matches[:8]}
    await update.message.reply_text(
        f"Найдено несколько транзакций. Выбери нужную:",
        reply_markup=InlineKeyboardMarkup(kb_rows),
    )
    return STATE_UPDATE_SELECT


async def handle_update_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    try:
        if msg.photo:
            photo = msg.photo[-1]
            tg_file = await photo.get_file()
            raw = await tg_file.download_as_bytearray()
            ctx.user_data["update_file_bytes"] = bytes(raw)
            ctx.user_data["update_mime_type"] = "image/jpeg"
            ctx.user_data["update_filename"] = f"{photo.file_id}.jpg"
        elif msg.document:
            doc = msg.document
            tg_file = await doc.get_file()
            raw = await tg_file.download_as_bytearray()
            ctx.user_data["update_file_bytes"] = bytes(raw)
            ctx.user_data["update_mime_type"] = doc.mime_type or "application/octet-stream"
            ctx.user_data["update_filename"] = doc.file_name or f"{doc.file_id}"
        else:
            await msg.reply_text("Пришли фото или файл документа.")
            return STATE_UPDATE_FILE
    except Exception as err:
        await msg.reply_text(f"❌ Ошибка загрузки: {err}")
        return STATE_UPDATE_FILE

    await msg.reply_text("Что это за документ?", reply_markup=kb_doc_type_update())
    return STATE_UPDATE_DOC_TYPE


async def cb_update_doc_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    doc_type = query.data.replace("updtype_", "")
    await query.edit_message_text("⏳ Распознаю документ и ищу транзакцию...")

    file_bytes = ctx.user_data.get("update_file_bytes")
    mime_type = ctx.user_data.get("update_mime_type", "image/jpeg")
    filename = ctx.user_data.get("update_filename", "receipt")

    # Parse with Claude Vision
    parsed = {}
    parse_failed = False
    try:
        if "image" in mime_type or "pdf" in mime_type:
            parsed = vision.parse_receipt(file_bytes, mime_type)
    except Exception:
        log.error(traceback.format_exc())
        parse_failed = True

    if "supplier_name" in parsed and not parsed.get("contractor_name"):
        parsed["contractor_name"] = parsed.pop("supplier_name")

    log.info(f"[UPDATE] Parsed from receipt: {parsed}")

    # Upload to Drive
    drive_url = ""
    try:
        drive_url = drive.upload_file(file_bytes, filename, mime_type, doc_type=doc_type)
    except Exception as up_err:
        log.warning(f"Drive upload failed in update: {up_err}")

    # Store parsed data — used by later steps (auto-match or manual fallback)
    ctx.user_data["update_parsed"] = parsed
    ctx.user_data["update_drive_url"] = drive_url
    ctx.user_data["update_doc_type"] = doc_type

    # Auto-search matching transactions
    matches = _find_matching_transactions(parsed)
    log.info(f"[UPDATE] Auto-match found {len(matches)} transaction(s)")

    if not matches:
        # No auto-match — fall back to manual ID entry
        if parse_failed or not parsed.get("date"):
            hint = (
                "⚠️ Не удалось распознать чек — сервис ИИ временно недоступен.\n\n"
                "Введи ID транзакции вручную (например <code>20260112001</code>):"
            )
        else:
            hint = (
                "🔍 Транзакция не найдена автоматически.\n\n"
                f"Дата из чека: <b>{html.escape(parsed.get('date', '?'))}</b> — "
                "убедись, что такая транзакция существует.\n\n"
                "Введи ID транзакции (например <code>20260112001</code>) или часть описания:"
            )
        await query.edit_message_text(hint, parse_mode="HTML")
        return STATE_UPDATE_SEARCH

    if len(matches) == 1:
        sheet_row, row = matches[0]
        ctx.user_data["update_sheet_row"] = sheet_row
        ctx.user_data["update_tx_row"] = row
        proposed, changes_text = _compute_update_proposed(parsed, drive_url, doc_type, row)
        tx_id = row[0] if row else "?"
        return await _show_update_confirm(
            lambda t, **kw: query.edit_message_text(t, **kw),
            lambda t, **kw: query.message.reply_text(t, **kw),
            ctx, proposed, changes_text, tx_id,
        )

    # Multiple matches — show list
    kb_rows = []
    for sheet_row, r in matches[:8]:
        tx_id = r[0] if r else "?"
        dt = r[1] if len(r) > 1 else ""
        amt = r[10] if len(r) > 10 else ""
        cur = r[11] if len(r) > 11 else ""
        label = f"{tx_id} | {dt} | {amt} {cur}"[:60]
        kb_rows.append([InlineKeyboardButton(label, callback_data=f"updsel_{sheet_row}")])

    ctx.user_data["update_matches"] = {sr: r for sr, r in matches[:8]}
    await query.edit_message_text(
        "Найдено несколько похожих транзакций. Выбери нужную:",
        reply_markup=InlineKeyboardMarkup(kb_rows),
    )
    return STATE_UPDATE_SELECT


async def cb_update_confirm_apply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    proposed   = ctx.user_data.get("update_proposed", {})
    changes_map = ctx.user_data.get("update_changes_map", {})
    selected   = ctx.user_data.get("update_selected", set(changes_map.keys()))
    sheet_row  = ctx.user_data.get("update_sheet_row")

    if not proposed or not sheet_row:
        await query.edit_message_text("❌ Нечего обновлять.")
        await query.message.reply_text("Главное меню:", reply_markup=kb_main())
        ctx.user_data.clear()
        return STATE_MAIN

    if not selected:
        await query.answer("Нет выбранных изменений — нечего применять.", show_alert=True)
        return STATE_UPDATE_CONFIRM

    # Build subset: selected cols + silent paired cols (F with I, L with K)
    subset = {
        col: val
        for col, (label, val) in proposed.items()
        if col in selected
        or (col == "F" and "I" in selected)   # supplier ID paired with name
        or (col == "L" and "K" in selected)   # currency paired with amount
    }

    try:
        sheets.update_expense_cells(sheet_row, subset)
        applied_lines = [changes_map[col] for col in selected if col in changes_map]
        await query.edit_message_text(
            "✅ <b>Обновлено!</b>\n\n"
            + "\n".join(f"• {_strip_html(t)}" for t in applied_lines),
            parse_mode="HTML",
        )
    except Exception as err:
        log.error(traceback.format_exc())
        await query.edit_message_text(f"❌ Ошибка обновления: {html.escape(str(err))}")

    await query.message.reply_text("Главное меню:", reply_markup=kb_main())
    ctx.user_data.clear()
    return STATE_MAIN


async def cb_update_confirm_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Отменено.")
    await query.message.reply_text("Главное меню:", reply_markup=kb_main())
    ctx.user_data.clear()
    return STATE_MAIN


# ── Error handler ─────────────────────────────────────────────────────────────

async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    log.error("Exception:", exc_info=ctx.error)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu),
            MessageHandler(filters.PHOTO | filters.Document.ALL, handle_file_or_text),
        ],
        states={
            STATE_MAIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu),
                MessageHandler(filters.PHOTO | filters.Document.ALL, handle_file_or_text),
            ],
            STATE_AWAIT_FILE_OR_TEXT: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, handle_file_or_text),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_file_or_text),
            ],
            STATE_CONFIRM_PARSED: [
                CallbackQueryHandler(cb_confirm, pattern="^confirm$"),
                CallbackQueryHandler(cb_edit, pattern="^edit$"),
                CallbackQueryHandler(cb_cancel, pattern="^cancel$"),
            ],
            STATE_EDIT_FIELD: [
                CallbackQueryHandler(cb_field_select, pattern="^field_"),
                CallbackQueryHandler(cb_back_confirm, pattern="^back_confirm$"),
                CallbackQueryHandler(cb_cancel, pattern="^cancel$"),
            ],
            STATE_EDIT_VALUE: [
                CallbackQueryHandler(cb_option_select, pattern="^opt_"),
                CallbackQueryHandler(cb_back_confirm, pattern="^back_confirm$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_value),
            ],
            STATE_AWAIT_DOC_TYPE_NEW: [
                CallbackQueryHandler(cb_doc_type_new, pattern="^doctype_"),
            ],
            STATE_ATTACH_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_attach_search),
                MessageHandler(filters.PHOTO | filters.Document.ALL, _warn_send_text_first),
            ],
            STATE_ATTACH_SELECT: [
                CallbackQueryHandler(cb_attach_select, pattern="^attach_"),
            ],
            STATE_ATTACH_DOC_TYPE: [
                CallbackQueryHandler(cb_attach_doc_type, pattern="^doctype_"),
            ],
            STATE_ATTACH_FILE: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, handle_attach_file),
            ],
            STATE_UPDATE_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_update_search),
                MessageHandler(filters.PHOTO | filters.Document.ALL, _warn_send_text_first),
            ],
            STATE_UPDATE_SELECT: [
                CallbackQueryHandler(cb_update_select, pattern="^updsel_"),
            ],
            STATE_UPDATE_FILE: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, handle_update_file),
            ],
            STATE_UPDATE_DOC_TYPE: [
                CallbackQueryHandler(cb_update_doc_type, pattern="^updtype_"),
            ],
            STATE_UPDATE_CONFIRM: [
                CallbackQueryHandler(cb_update_toggle,        pattern="^updtoggle_"),
                CallbackQueryHandler(cb_update_confirm_apply, pattern="^updconfirm$"),
                CallbackQueryHandler(cb_update_confirm_cancel, pattern="^updcancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("start", cmd_start),
        ],
        per_chat=True,
        per_message=False,
    )

    app.add_handler(conv)
    app.add_error_handler(error_handler)

    # Pre-warm Google API services so the first user request doesn't block
    # the async event loop waiting for the discovery document HTTP call.
    try:
        sheets._get_service()
        drive._get_service()
        log.info("Google API services pre-warmed OK")
    except Exception as warm_err:
        log.warning(f"Could not pre-warm Google API: {warm_err}")

    log.info("Bot started. Polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    import asyncio
    # Python 3.10+ requires explicit event loop in main thread
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
