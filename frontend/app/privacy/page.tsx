"use client";

import LanguageSwitcher from "../../components/LanguageSwitcher";
import { useI18n } from "../../lib/i18n";

const SECTIONS = {
  en: [
    ["1. What we collect", "Your account email; the text you paste or upload; the scores, suggestions and rewrites we generate; usage records; and your language/consent preferences."],
    ["2. How we use it", "To score and rewrite your copy, operate the free daily quota, prevent abuse, and support you. We do not sell your data."],
    ["3. AI processing", "Your text is sent to a third-party AI model to produce scores and rewrites. We send only what the requested feature needs."],
    ["4. Improving the service", "By default, anonymized copies and their scores help us learn what works. You can opt out per document or anytime; opting out removes the stored corpus features for that document."],
    ["5. Retention & deletion", "Documents are deleted when you delete them or your account. Derived corpus features are removed when you opt out or delete the document."],
    ["6. Cookies", "We use a language cookie and session tokens to keep you signed in. No third-party advertising cookies."],
    ["7. Anonymous traffic statistics", "We count page views with a first-party, cookie-less method: each visit stores only the page path, the referring site, and a salted hash derived from your IP address, browser user-agent and the current month. Raw IP addresses are not stored, the hash cannot be reversed, and it rotates every month so visits cannot be linked across months. This data is never used to identify you or for advertising."],
    ["8. Your rights", "You can access, correct, export and delete your data from the app. Where GDPR/CCPA apply you have rights to access, portability, erasure and objection."],
    ["9. Contact", "Privacy requests: reach us from inside the product. A dedicated privacy contact will be finalized before public launch."],
  ],
  zh: [
    ["1. 我们收集什么", "你的账号邮箱；你粘贴或上传的文本；我们生成的评分、建议与改写；使用记录；以及你的语言/授权偏好。"],
    ["2. 我们如何使用", "用于对你的文案评分与改写、执行每日免费额度、防滥用与客户支持。我们不会出售你的数据。"],
    ["3. AI 处理", "你的文本会发送给第三方 AI 模型以生成评分与改写；我们只发送所请求功能所需的内容。"],
    ["4. 改进服务", "默认情况下，匿名文案及其评分会帮助我们总结规律。你可以对单篇或随时关闭；关闭后会移除该文档已存的语料特征。"],
    ["5. 保留与删除", "当你删除文档或账号时，文档会被删除；当你关闭授权或删除文档时，派生的语料特征会被移除。"],
    ["6. Cookie", "我们使用语言 cookie 与会话令牌以保持登录状态；不使用第三方广告 cookie。"],
    ["7. 匿名访问统计", "我们以第一方、无 cookie 的方式统计访问量：每次访问仅记录页面路径、来源站点，以及由「IP 地址 + 浏览器标识 + 当前月份」经加盐哈希得到的匿名标识。我们不保存明文 IP，该哈希不可逆，且按月轮换，无法跨月关联你的访问。此数据不会用于识别你个人，也不用于广告。"],
    ["8. 你的权利", "你可在应用内访问、更正、导出与删除你的数据。在适用 GDPR/CCPA 时，你享有访问、可携、删除与反对处理的权利。"],
    ["9. 联系我们", "隐私相关请求可在产品内联系我们；专门的隐私联系方式将在正式上线前确定。"],
  ],
} as const;

export default function PrivacyPage() {
  const { locale, t } = useI18n();
  const sections = SECTIONS[locale] ?? SECTIONS.en;
  return (
    <main className="min-h-full bg-white font-sans text-zinc-900 antialiased">
      <header className="sticky top-0 z-20 border-b border-black/5 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 w-full max-w-3xl items-center justify-between px-6">
          <a href="/" className="flex items-center gap-2 text-[15px] font-semibold tracking-tight">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-zinc-800 to-zinc-950 text-sm font-bold text-white">NB</span>
            {t("common.app_name")}
          </a>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <a href="/studio" className="rounded-full bg-zinc-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-zinc-700">
              {locale === "zh" ? "打开工作台" : "Open Studio"}
            </a>
          </div>
        </div>
      </header>
      <article className="mx-auto max-w-3xl px-6 py-14">
        <h1 className="text-3xl font-semibold tracking-tight">{locale === "zh" ? "隐私政策" : "Privacy Policy"}</h1>
        <p className="mt-2 text-sm text-zinc-400">NotesBang · 2026-09-17</p>
        <div className="mt-8 space-y-6 text-[15px] leading-relaxed text-zinc-600">
          {sections.map(([title, body]) => (
            <section key={title}>
              <h2 className="text-[17px] font-semibold text-zinc-900">{title}</h2>
              <p className="mt-1.5">{body}</p>
            </section>
          ))}
        </div>
      </article>
    </main>
  );
}
