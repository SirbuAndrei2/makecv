import { readFileSync } from 'node:fs'
import { afterEach, describe, expect, it } from 'vitest'
import { loadApp } from './load-app.js'

// The /ro and /ru builders are generated from index.html by tools/build_i18n.py (run `python3 tools/build_pages.py`
// after editing index.html or tools/i18n/*). These tests load the generated files the same way form.test.js loads
// the English one, so they also catch a stale or broken generation.
const LANGS = {
  ro: {
    file: 'ro/index.html',
    url: 'https://makecv.org/ro',
    nameErr: 'Scrie numele complet (cel puțin 3 caractere).',
    headings: ['Profil profesional', 'Experiență profesională', 'Educație', 'Proiecte', 'Competențe', 'Limbi cunoscute', 'Certificări'],
    dates: 'mar. 2022 – prezent',
    native: 'Nativ',
    levels: ['Începător', 'Mediu', 'Avansat'],
    missing: ['numele complet', 'o adresă de email', 'cel puțin un loc de muncă sau o școală'],
    ui: { 'sec-personal': 'Date personale', 'btn-exp': 'Adaugă experiență', 'dl-txt': 'Descarcă PDF', 'step2-heading': 'Alege modelul de CV', 'faq-heading': 'Întrebări frecvente' },
    summary: '1 loc de muncă · 2 școli',
    chars: '20 de caractere · cam scurt',
  },
  ru: {
    file: 'ru/index.html',
    url: 'https://makecv.org/ru',
    nameErr: 'Укажите имя и фамилию (не меньше 3 символов).',
    headings: ['О себе', 'Опыт работы', 'Образование', 'Проекты', 'Навыки', 'Языки', 'Сертификаты'],
    dates: 'март 2022 – по наст. время',
    native: 'Родной',
    levels: ['Начальный', 'Средний', 'Продвинутый'],
    missing: ['имя и фамилию', 'email', 'хотя бы одно место работы или учёбы'],
    ui: { 'sec-personal': 'Личные данные', 'btn-exp': 'Добавить место работы', 'dl-txt': 'Скачать PDF', 'faq-heading': 'Частые вопросы' },
    summary: '1 место работы · 2 учебных заведения',
    chars: '20 символов · коротковато',
  },
}

// Visible English strings of index.html that must never reach a translated page.
const ENGLISH = ['Personal information', 'Add experience', 'Choose template', 'Download PDF', 'Work experience',
  'Professional summary', 'Frequently Asked Questions', 'How to Build Your Resume', 'Optional sections',
  'Accept All', 'Privacy Policy', 'Remove photo', 'Start typing', 'resumes created this month', 'What People Are Saying']

describe.each(Object.entries(LANGS))('%s builder', (lang, t) => {
  let app
  afterEach(() => app?.close())
  const html = readFileSync(new URL('../' + t.file, import.meta.url), 'utf8')

  it('should declare its language, canonical and hreflang alternates', () => {
    expect(html).toMatch(new RegExp(`<html lang="${lang}">`))
    expect(html).toContain(`<link rel="canonical" href="${t.url}">`)
    for (const [hl, href] of [['en', 'https://makecv.org/'], ['ro', 'https://makecv.org/ro'], ['ru', 'https://makecv.org/ru'], ['x-default', 'https://makecv.org/']])
      expect(html).toContain(`<link rel="alternate" hreflang="${hl}" href="${href}">`)
  })

  it('should mirror the visible FAQ word for word in the FAQPage JSON-LD', () => {
    app = loadApp({ file: t.file, url: t.url })
    const d = app.window.document
    const visible = [...d.querySelectorAll('.faq-item')].map(i => [i.querySelector('dt').textContent.trim(), i.querySelector('dd').textContent.replace(/\s+/g, ' ').trim()])
    const ld = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map(m => JSON.parse(m[1])).find(x => x['@type'] === 'FAQPage')
    expect(visible.length).toBeGreaterThan(5)
    expect(ld.mainEntity.map(q => [q.name, q.acceptedAnswer.text])).toEqual(visible)
  })

  it('should show translated validation messages on blur', () => {
    app = loadApp({ file: t.file, url: t.url })
    app.type('f-name', 'Al')
    app.blur('f-name')
    expect(app.$('f-name').getAttribute('aria-invalid')).toBe('true')
    expect(app.$('f-name-err').textContent.trim()).toBe(t.nameErr)
  })

  it('should list what blocks the download in the page language', () => {
    app = loadApp({ file: t.file, url: t.url })
    app.window.goStep(3)
    expect([...app.$('valid-msg').querySelectorAll('button')].map(b => b.textContent)).toEqual(t.missing)
  })

  it('should translate the key UI strings and leave no English behind', () => {
    app = loadApp({ file: t.file, url: t.url })
    for (const [id, text] of Object.entries(t.ui)) expect(app.$(id).textContent.trim()).toContain(text)
    const body = app.window.document.body.cloneNode(true)
    body.querySelectorAll('script').forEach(s => s.remove())
    const visible = body.textContent
    for (const en of ENGLISH) expect(visible).not.toContain(en)
  })

  it('should render the resume headings, dates and levels in the page language', () => {
    app = loadApp({ file: t.file, url: t.url })
    app.window.eval(`
      cv.personal.name = 'Test Person'; cv.personal.email = 't@example.com'; cv.summary = 'Summary text';
      cv.experience = [{ title: 'Analyst', company: 'X', startMonth: '3', startYear: '2022', endMonth: '', endYear: '', current: true, location: '', description: '' }];
      cv.education = [{ degree: 'BSc', institution: 'U', startYear: '2018', endYear: '2021', current: false, notes: '' }, { degree: 'MSc', institution: 'U', startYear: '2021', endYear: '', current: true, notes: '' }];
      cv.skills = [{ name: 'SQL', level: 'Avansat' }];
      cv.languages = [{ name: 'X', level: 'Native' }];
      cv.projects = [{ name: 'P', description: '', url: '', tech: '' }];
      cv.certifications = [{ name: 'C', org: '', year: '2024', url: '' }];
    `)
    app.window.selTpl('clasic')
    app.window.goStep(3)
    const preview = app.$('cv-preview')
    const titles = [...preview.querySelectorAll('.sec-title')].map(s => s.textContent.trim())
    for (const h of t.headings) expect(titles).toContain(h)
    expect(preview.textContent).toContain(t.dates)
    expect(preview.textContent).toContain(t.native)
    for (const en of ['Work Experience', 'Education', 'Skills', 'Languages', 'Present', 'Native']) expect(preview.textContent).not.toContain(en)
    // the Modern template labels the summary as its profile heading
    app.window.selTpl('modern')
    expect(app.$('dl-btn').disabled).toBe(false)
    expect(app.$('data-sum').textContent).toContain(t.summary)
  })

  it('should keep storing skill levels as the Romanian values barW() expects, with translated labels', () => {
    app = loadApp({ file: t.file, url: t.url })
    app.type('skill-inp', 'SQL')
    app.key('skill-inp', 'Enter')
    expect(app.state().skills[0].level).toBe('Mediu')
    const select = app.$('skills-wrap').querySelector('select')
    expect([...select.options].map(o => [o.value, o.textContent])).toEqual([['Începător', t.levels[0]], ['Mediu', t.levels[1]], ['Avansat', t.levels[2]]])
    app.choose(select, 'Avansat')
    expect(app.state().skills[0].level).toBe('Avansat')
    expect(app.window.barW(app.state().skills[0].level)).toBe(92)
  })

  it('should count summary characters with the language plural rules', () => {
    app = loadApp({ file: t.file, url: t.url })
    app.type('f-summary', 'x'.repeat(20))
    expect(app.$('char-cnt').textContent).toBe(t.chars)
  })

  it('should preselect a template from ?template=', () => {
    app = loadApp({ file: t.file, url: t.url + '?template=harvard' })
    expect(app.state().selectedTemplate).toBe('harvard')
  })
})
