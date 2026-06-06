#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

SUPPORTED_LANGUAGES = ("zh", "en")
DEFAULT_LANGUAGE = "zh"


TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh": {
        "language.zh": "中文",
        "language.en": "English",
        "home.default_title": "欢迎选购",
        "home.default_intro": "请选择下方商品进行购买",
        "home.choose_product": "请选择商品：",
        "home.language_label": "语言 / Language",
        "common.back": "⬅️ 返回",
        "common.support": "💁联系客服",
        "common.buy": "🛒 购买",
        "common.unknown": "未知",
        "support.not_configured": "ℹ️ 暂未配置客服联系方式。",
        "support.title": "🆘 客服\n点击下方按钮",
        "support.contact": "🆘 客服联系方式：\n{contact}",
        "support.failed": "❗ 获取客服信息失败，请稍后重试。",
        "product.unavailable": "⚠️ 商品不存在或已下架",
        "product.no_tiers": "暂无可购买档位",
        "product.price_tiers": "💰 价格档位：",
        "product.detail_caption": " {name}\n\n{description}\n\n{price_title}\n{price_text}",
        "payment.choose_method": "商品：{subject}\n价格：¥{price}\n💳 请选择支付方式：",
        "payment.generating": "⏳ 正在生成付款链接，请稍候…\n请勿重复点击按钮，预计几秒完成。",
        "payment.min_amount": "❌ 该通道最小支付金额为 3.00 元，请返回重新选择支付方式或购买金额≥3.00 的商品。",
        "payment.usdt_min_amount": "❌ 当前商品折算后约 {converted_amount} USDT，低于USDT最小支付金额 {min_amount} USDT。\n请返回选择其它支付方式或购买更高金额的商品。",
        "payment.create_failed": "❌ 下单失败：{error}\n请稍后重试，或返回重新选择支付方式。",
        "payment.acknowledged": "✅ 已确认",
        "payment.order_no": "🧾 订单号：{out_trade_no}",
        "payment.product_name": "📦 商品名：{subject}",
        "payment.product_detail": "📝 商品详情：{detail}",
        "payment.price": "💰 价格：¥{price}",
        "payment.method": "💳 支付方式：{method}",
        "payment.wallet": "📍 USDT钱包地址：`{address}`",
        "payment.usdt_direct_amount": "💰 实际支付金额：`{amount} USDT`",
        "payment.link": "🔗 支付链接：{url}",
        "payment.timeout": "⏱️ 订单有效期约 {minutes} 分钟，超时将自动取消。",
        "payment.usdt_qr_hint": "提示：扫描上方二维码完成USDT支付，支付成功后请返回本聊天等待邀请链接。",
        "payment.usdt_link_hint": "提示：点击链接完成USDT支付，支付成功后系统会自动检测并发送邀请链接。",
        "payment.qr_caption": "📷 请扫码支付 ¥{price}\n🧾 订单号：{out_trade_no}\n⏱️ 订单有效期约 {minutes} 分钟，超时将自动取消。\n提示：支付成功后我会自动发送自动拉群邀请链接。",
        "payment.link_hint": "提示：若链接无法直接打开，可复制到浏览器；完成支付后请返回本聊天等待邀请链接。",
        "payment.link_popup_hint": "提示：请点击下方「跳转支付」按钮打开支付页；完成支付后请返回本聊天等待邀请链接。",
        "payment.open_pay_button": "💳 跳转支付",
        "payment.open_pay_expired": "支付链接已失效，请返回重新下单。",
        "payment.open_pay_missing": "支付链接未生成，请重新选择支付宝。",
        "payment.open_pay_failed": "无法打开支付页，请稍后重试或复制链接到浏览器。",
        "payment.cancelled": "✅ 已取消订单，正在返回商品列表…",
        "payment.confirm_cancel": "✅ 确定取消",
        "payment.continue_pay": "↩️ 继续付款",
        "payment.confirm_leave": "✅ 确定离开",
        "payment.stay_pay": "↩️ 留在付款台",
        "payment.recheck_too_fast": "⏳ 操作过于频繁，请稍后再试…",
        "payment.order_not_found": "未找到该订单，请返回重试。",
        "payment.expired": "⏱️ 订单已超时并取消，请返回重新下单。",
        "payment.not_paid": "尚未检测到支付成功，请完成支付后再点“🔄 我已支付，重新检查”。",
        "payment.current_status": "当前订单状态：{status}",
        "payment.recheck_button": "🔄 我已支付，重新检查",
        "payment.cancel_button": "❌ 取消本次付款",
        "announcement.usdt_trc20_direct_default": "请务必选择 TRC20 网络，并严格按上方实际支付金额付款。\n二维码仅包含收款地址，付款金额请手动填写。\n到账后系统会自动检测并发货，请勿重复下单。",
        "announcement.kavip_alipay_default": "请按页面提示完成支付宝付款。\n付款成功后请返回本聊天等待系统自动发货。",
        "announcement.usdt_default": "请务必选择 TRC20 网络，并严格按上方实际支付金额付款。\n二维码仅包含收款地址，付款金额请手动填写。\n到账后系统会自动检测并发货，请勿重复下单。",
        "announcement.rmb_default": "请按页面提示完成支付宝付款。\n付款成功后请返回本聊天等待系统自动发货。",
        "delivery.group_success": "🎉 已成功进群：{title}\n🔒 一次性邀请链接将自动撤销\n✅ 订单已完成 感谢支持！！！",
        "status.pending": "待支付",
        "status.paid": "已支付",
        "status.processing": "处理中",
        "status.completed": "已完成",
        "status.cancelled": "已取消",
        "status.expired": "已超时",
        "status.refunded": "已退款",
        "status.failed": "支付失败",
    },
    "en": {
        "language.zh": "中文",
        "language.en": "English",
        "home.default_title": "Welcome",
        "home.default_intro": "Please choose a product below",
        "home.choose_product": "Choose a product:",
        "home.language_label": "Language / 语言",
        "common.back": "⬅️ Back",
        "common.support": "💁 Contact Support",
        "common.buy": "🛒 Buy",
        "common.unknown": "Unknown",
        "support.not_configured": "ℹ️ Support contact has not been configured.",
        "support.title": "🆘 Support\nTap the button below",
        "support.contact": "🆘 Support contact:\n{contact}",
        "support.failed": "❗ Failed to get support info. Please try again later.",
        "product.unavailable": "⚠️ Product is unavailable or has been removed",
        "product.no_tiers": "No purchasable tiers yet",
        "product.price_tiers": "💰 Price tiers:",
        "product.detail_caption": " {name}\n\n{description}\n\n{price_title}\n{price_text}",
        "payment.choose_method": "Product: {subject}\nPrice: ¥{price}\n💳 Please choose a payment method:",
        "payment.generating": "⏳ Generating payment link, please wait...\nPlease do not tap repeatedly. This should take a few seconds.",
        "payment.min_amount": "❌ This channel requires a minimum payment of 3.00 CNY. Please go back and choose another payment method or buy a product priced at least 3.00 CNY.",
        "payment.usdt_min_amount": "❌ This product converts to about {converted_amount} USDT, which is below the minimum USDT payment amount of {min_amount} USDT.\nPlease choose another payment method or buy a higher-priced product.",
        "payment.create_failed": "❌ Failed to create order: {error}\nPlease try again later or choose another payment method.",
        "payment.acknowledged": "✅ Confirmed",
        "payment.order_no": "🧾 Order No.: {out_trade_no}",
        "payment.product_name": "📦 Product: {subject}",
        "payment.product_detail": "📝 Details: {detail}",
        "payment.price": "💰 Price: ¥{price}",
        "payment.method": "💳 Payment method: {method}",
        "payment.wallet": "📍 USDT wallet address: `{address}`",
        "payment.usdt_direct_amount": "💰 Exact payment amount: `{amount} USDT`",
        "payment.link": "🔗 Payment link: {url}",
        "payment.timeout": "⏱️ Order expires in about {minutes} minutes and will be cancelled automatically.",
        "payment.usdt_qr_hint": "Tip: scan the QR code above to complete USDT payment, then return to this chat and wait for the invite link.",
        "payment.usdt_link_hint": "Tip: open the link to complete USDT payment. The system will detect payment and send the invite link automatically.",
        "payment.qr_caption": "📷 Please scan to pay ¥{price}\n🧾 Order No.: {out_trade_no}\n⏱️ Order expires in about {minutes} minutes and will be cancelled automatically.\nTip: after payment succeeds, I will send the group invite link automatically.",
        "payment.link_hint": "Tip: if the link cannot be opened directly, copy it into your browser. After payment, return to this chat and wait for the invite link.",
        "payment.link_popup_hint": "Tip: tap \"Open payment\" below to open the payment page. After payment, return to this chat and wait for the invite link.",
        "payment.open_pay_button": "💳 Open payment",
        "payment.open_pay_expired": "The payment link has expired. Please go back and place a new order.",
        "payment.open_pay_missing": "Payment link was not generated. Please select Alipay again.",
        "payment.open_pay_failed": "Could not open the payment page. Please try again or copy the link to your browser.",
        "payment.cancelled": "✅ Order cancelled. Returning to product list...",
        "payment.confirm_cancel": "✅ Cancel order",
        "payment.continue_pay": "↩️ Continue payment",
        "payment.confirm_leave": "✅ Leave",
        "payment.stay_pay": "↩️ Stay on payment page",
        "payment.recheck_too_fast": "⏳ Too many attempts. Please try again later...",
        "payment.order_not_found": "Order not found. Please go back and try again.",
        "payment.expired": "⏱️ The order has expired and was cancelled. Please place a new order.",
        "payment.not_paid": "Payment has not been detected yet. Please complete payment, then tap \"🔄 I have paid, recheck\".",
        "payment.current_status": "Current order status: {status}",
        "payment.recheck_button": "🔄 I have paid, recheck",
        "payment.cancel_button": "❌ Cancel this payment",
        "announcement.usdt_trc20_direct_default": "Please use the TRC20 network and pay the exact amount shown above.\nThe QR code contains only the receiving address. Enter the amount manually.\nThe system will detect the payment and deliver automatically. Please do not place duplicate orders.",
        "announcement.kavip_alipay_default": "Please complete the Alipay payment as instructed on the payment page.\nAfter payment succeeds, return to this chat and wait for automatic delivery.",
        "announcement.usdt_default": "Please use the TRC20 network and pay the exact amount shown above.\nThe QR code contains only the receiving address. Enter the amount manually.\nThe system will detect the payment and deliver automatically. Please do not place duplicate orders.",
        "announcement.rmb_default": "Please complete the Alipay payment as instructed on the payment page.\nAfter payment succeeds, return to this chat and wait for automatic delivery.",
        "delivery.group_success": "🎉 Joined successfully: {title}\n🔒 The one-time invite link will be revoked automatically\n✅ Order completed. Thank you!",
        "status.pending": "Pending",
        "status.paid": "Paid",
        "status.processing": "Processing",
        "status.completed": "Completed",
        "status.cancelled": "Cancelled",
        "status.expired": "Expired",
        "status.refunded": "Refunded",
        "status.failed": "Payment failed",
    },
}


def normalize_language(language: Any) -> str:
    raw = str(language or "").strip().lower().replace("_", "-")
    if raw.startswith("en"):
        return "en"
    if raw.startswith("zh") or raw in {"cn", "中文"}:
        return "zh"
    return DEFAULT_LANGUAGE


def t(key: str, language: Any = DEFAULT_LANGUAGE, **kwargs: Any) -> str:
    lang = normalize_language(language)
    template = TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS[DEFAULT_LANGUAGE].get(key) or key
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def language_button_label(language: Any, selected_language: Any | None = None) -> str:
    lang = normalize_language(language)
    label = t(f"language.{lang}", lang)
    return f"✅ {label}" if selected_language and normalize_language(selected_language) == lang else label
