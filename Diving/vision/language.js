export const lang = document.documentElement.lang.startsWith('en') ? 'en' : 'zh';
export const t = (zh, en) => lang === 'en' ? en : zh;
