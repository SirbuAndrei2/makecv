import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { loadApp } from './load-app.js'

let app
beforeEach(() => { app = loadApp() })
afterEach(() => { app.close(); vi.useRealTimers() })

const err = id => ({
  invalid: app.$(id).getAttribute('aria-invalid'),
  shown: app.$(id + '-err').classList.contains('show'),
})

describe('personal details', () => {
  it.each([
    ['f-name', 'name', 'Ana Popescu'],
    ['f-title', 'title', 'Data Analyst'],
    ['f-email', 'email', 'ana@example.com'],
    ['f-phone', 'phone', '+40 721 000 000'],
    ['f-city', 'city', 'Cluj-Napoca'],
    ['f-linkedin', 'linkedin', 'linkedin.com/in/ana'],
    ['f-website', 'website', 'ana.dev'],
  ])('should store #%s in cv.personal.%s when typed', (id, key, value) => {
    app.type(id, value)
    expect(app.state().personal[key]).toBe(value)
  })

  it('should store the summary when typed', () => {
    app.type('f-summary', 'Analyst with 5 years in retail.')
    expect(app.state().summary).toBe('Analyst with 5 years in retail.')
  })
})

describe('inline validation', () => {
  it('should flag a name shorter than 3 characters on blur', () => {
    app.type('f-name', 'Al')
    app.blur('f-name')
    expect(err('f-name')).toEqual({ invalid: 'true', shown: true })
  })

  it('should count only non-space characters toward the name minimum', () => {
    app.type('f-name', '  Al  ')
    app.blur('f-name')
    expect(err('f-name').invalid).toBe('true')
  })

  it('should not flag an empty field on blur', () => {
    app.blur('f-name')
    app.blur('f-email')
    expect(err('f-name')).toEqual({ invalid: null, shown: false })
    expect(err('f-email')).toEqual({ invalid: null, shown: false })
  })

  it.each(['ana', 'ana@', 'ana@example', '@example.com', 'ana @example.com'])(
    'should flag the email %j on blur', value => {
      app.type('f-email', value)
      app.blur('f-email')
      expect(err('f-email')).toEqual({ invalid: 'true', shown: true })
    })

  it('should accept a valid email with surrounding spaces', () => {
    app.type('f-email', ' ana@example.com ')
    app.blur('f-email')
    expect(err('f-email')).toEqual({ invalid: 'false', shown: false })
  })

  it('should clear the error while typing once the value becomes valid', () => {
    app.type('f-email', 'ana@')
    app.blur('f-email')
    app.type('f-email', 'ana@example.com')
    expect(err('f-email')).toEqual({ invalid: 'false', shown: false })
  })

  it('should keep the error while the value typed is still invalid', () => {
    app.type('f-name', 'A')
    app.blur('f-name')
    app.type('f-name', 'An')
    expect(err('f-name')).toEqual({ invalid: 'true', shown: true })
  })

  it('should not show an error while typing before the first blur', () => {
    app.type('f-email', 'an')
    expect(err('f-email')).toEqual({ invalid: null, shown: false })
  })
})

describe('summary character count', () => {
  const counter = () => app.$('char-cnt')

  it.each([
    [0, '0 characters', 'text-slate-500'],
    [1, '1 characters · a bit short', 'text-amber-700'],
    [299, '299 characters · a bit short', 'text-amber-700'],
    [300, '300 characters', 'text-emerald-700'],
    [500, '500 characters', 'text-emerald-700'],
    [501, '501 characters · try to trim', 'text-red-600'],
  ])('should show %i characters as %j in %s', (n, text, colour) => {
    app.type('f-summary', 'x'.repeat(n))
    expect(counter().textContent).toBe(text)
    expect(counter().classList.contains(colour)).toBe(true)
  })
})

describe('repeatable entries', () => {
  const cards = list => app.$(list).querySelectorAll('.entry-card')

  it('should add an experience card and focus its first field', () => {
    app.click('btn-exp')
    expect(cards('exp-list')).toHaveLength(1)
    expect(app.window.document.activeElement.id).toBe('x-experience-0-title')
  })

  it.each([
    ['experience', 'btn-exp', 'exp-list', 5],
    ['education', 'btn-edu', 'edu-list', 3],
    ['languages', 'btn-lang', 'lang-list', 4],
    ['projects', 'btn-proj', 'proj-list', 3],
    ['certifications', 'btn-cert', 'cert-list', 4],
  ])('should cap %s at %i entries and hide the add button', (type, btn, list, max) => {
    for (let i = 0; i < max + 2; i++) app.click(btn)
    expect(app.state()[type]).toHaveLength(max)
    expect(cards(list)).toHaveLength(max)
    expect(app.$(btn).style.display).toBe('none')
  })

  it('should show the add button again after removing an entry at the cap', () => {
    for (let i = 0; i < 3; i++) app.click('btn-edu')
    app.click(cards('edu-list')[0].querySelector('.btn-del'))
    expect(app.state().education).toHaveLength(2)
    expect(app.$('btn-edu').style.display).toBe('flex')
  })

  it('should remove the chosen entry and renumber the rest', () => {
    for (let i = 0; i < 3; i++) app.click('btn-exp')
    ;['First', 'Second', 'Third'].forEach((t, i) => app.type(`x-experience-${i}-title`, t))
    app.click(cards('exp-list')[1].querySelector('.btn-del'))
    expect(app.state().experience.map(x => x.title)).toEqual(['First', 'Third'])
    expect(app.$('x-experience-1-title').value).toBe('Third')
    expect([...app.$('exp-list').querySelectorAll('.entry-num')].map(n => n.textContent)).toEqual(['Experience 1', 'Experience 2'])
  })

  it('should store typed entry fields on the right entry', () => {
    app.click('btn-exp'); app.click('btn-exp')
    app.type('x-experience-1-company', 'Acme')
    app.type('x-experience-1-description', 'Led X\nShipped Y')
    expect(app.state().experience[0].company).toBe('')
    expect(app.state().experience[1]).toMatchObject({ company: 'Acme', description: 'Led X\nShipped Y' })
  })

  it('should start a language at level B1 and store the chosen level', () => {
    app.click('btn-lang')
    expect(app.$('x-languages-0-level').value).toBe('B1')
    app.choose(app.$('x-languages-0-level'), 'C1')
    expect(app.state().languages[0].level).toBe('C1')
  })

  describe('experience dates', () => {
    const card = () => cards('exp-list')[0]
    const sel = label => card().querySelector(`select[aria-label="${label}"]`)

    beforeEach(() => {
      app.click('btn-exp')
      app.choose(sel('Start month'), '3')
      app.choose(sel('Start year'), '2022')
    })

    it('should store month and year as chosen', () => {
      expect(app.state().experience[0]).toMatchObject({ startMonth: '3', startYear: '2022' })
    })

    it('should store "current" as a boolean and disable the end date', () => {
      app.check(card().querySelector('input[type=checkbox]'), true)
      expect(app.state().experience[0].current).toBe(true)
      expect(sel('End month').disabled).toBe(true)
      expect(sel('End year').disabled).toBe(true)
    })

    it('should keep the chosen dates and typed text when the list re-renders', () => {
      app.type('x-experience-0-title', 'Analyst')
      app.click('btn-exp')
      expect(sel('Start month').value).toBe('3')
      expect(sel('Start year').value).toBe('2022')
      expect(app.$('x-experience-0-title').value).toBe('Analyst')
    })
  })

  it('should keep quotes and markup in an entry as plain text after a re-render', () => {
    app.click('btn-exp')
    const nasty = 'Dev "Lead" <img src=x onerror=alert(1)> & co'
    app.type('x-experience-0-title', nasty)
    app.click('btn-exp')
    expect(app.$('x-experience-0-title').value).toBe(nasty)
    expect(app.$('exp-list').querySelector('img')).toBeNull()
  })
})

describe('skills', () => {
  const pills = () => [...app.$('skills-wrap').querySelectorAll('.skill-pill span')].map(s => s.textContent)

  it('should add the typed skill on Enter and clear the input', () => {
    app.type('skill-inp', 'SQL')
    app.key('skill-inp', 'Enter')
    expect(pills()).toEqual(['SQL'])
    expect(app.$('skill-inp').value).toBe('')
  })

  it('should add the typed skill on a comma', () => {
    app.type('skill-inp', 'Excel')
    app.key('skill-inp', ',')
    expect(pills()).toEqual(['Excel'])
  })

  it('should not add a skill on other keys', () => {
    app.type('skill-inp', 'Exc')
    app.key('skill-inp', 'e')
    expect(pills()).toEqual([])
  })

  it('should split a pasted comma list on the Add button', () => {
    app.type('skill-inp', 'React, Node.js ,, SQL')
    app.click(app.$('skill-inp').nextElementSibling)
    expect(pills()).toEqual(['React', 'Node.js', 'SQL'])
    expect(app.$('skill-inp').value).toBe('')
  })

  it('should ignore blanks and case-insensitive duplicates', () => {
    app.type('skill-inp', 'sql, SQL,  , Sql')
    app.click(app.$('skill-inp').nextElementSibling)
    expect(pills()).toEqual(['sql'])
  })

  it('should store levels as the Romanian strings barW() expects', () => {
    app.type('skill-inp', 'SQL')
    app.key('skill-inp', 'Enter')
    expect(app.state().skills[0].level).toBe('Mediu')
    app.choose(app.$('skills-wrap').querySelector('select'), 'Avansat')
    expect(app.state().skills[0].level).toBe('Avansat')
  })

  it('should remove a skill with its × button', () => {
    app.type('skill-inp', 'A1x, B2y')
    app.click(app.$('skill-inp').nextElementSibling)
    app.click(app.$('skills-wrap').querySelector('button'))
    expect(pills()).toEqual(['B2y'])
  })

  it('should render a skill name as text, not markup', () => {
    app.type('skill-inp', '<b>bold</b>')
    app.key('skill-inp', 'Enter')
    expect(pills()).toEqual(['<b>bold</b>'])
    expect(app.$('skills-wrap').querySelector('b')).toBeNull()
  })
})

describe('photo', () => {
  async function upload() {
    const file = new app.window.File(['img'], 'me.png', { type: 'image/png' })
    const input = app.$('photo-input')
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new app.window.Event('change'))
    await vi.waitFor(() => expect(app.state().personal.photo).toMatch(/^data:image\/png;base64,/))
  }

  it('should store the uploaded photo as a data URL and show it', async () => {
    await upload()
    expect(app.$('photo-img').style.display).toBe('block')
    expect(app.$('photo-rm').classList.contains('hidden')).toBe(false)
  })

  it('should clear the photo and restore the placeholder on remove', async () => {
    await upload()
    app.click('photo-rm')
    expect(app.state().personal.photo).toBeNull()
    expect(app.$('photo-img').hasAttribute('src')).toBe(false)
    expect(app.$('photo-ph').style.display).toBe('')
    expect(app.$('photo-rm').classList.contains('hidden')).toBe(true)
  })
})

describe('download gate (step 3)', () => {
  const fillValid = () => {
    app.type('f-name', 'Ana Popescu')
    app.type('f-email', 'ana@example.com')
    app.click('btn-edu')
  }
  const gate = () => {
    app.window.goStep(3)
    return {
      disabled: app.$('dl-btn').disabled && app.$('ats-btn').disabled,
      asks: [...app.$('valid-msg').querySelectorAll('button')].map(b => b.textContent),
    }
  }

  it('should enable both downloads when name, email and one job or school are filled', () => {
    fillValid()
    expect(gate()).toEqual({ disabled: false, asks: [] })
  })

  it('should list everything missing on an empty form', () => {
    expect(gate()).toEqual({ disabled: true, asks: ['your full name', 'an email address', 'at least one job or school'] })
  })

  it('should accept an experience entry instead of education', () => {
    app.type('f-name', 'Ana Popescu')
    app.type('f-email', 'ana@example.com')
    app.click('btn-exp')
    expect(gate().disabled).toBe(false)
  })

  it('should send the visitor back to the missing field and flag it', () => {
    vi.useFakeTimers()
    app.type('f-email', 'ana@example.com')
    app.click('btn-edu')
    app.click(gate().asks.length && app.$('valid-msg').querySelector('button'))
    vi.advanceTimersByTime(350)
    expect(app.window.document.body.dataset.step).toBe('1')
    expect(app.window.document.activeElement.id).toBe('f-name')
    expect(err('f-name')).toEqual({ invalid: 'true', shown: true })
  })
})

describe('live preview debounce (≥1280px)', () => {
  beforeEach(() => {
    app.close()
    vi.useFakeTimers()
    app = loadApp({ wide: true })
  })

  it('should render the typed name only after 250 ms of quiet', () => {
    app.type('f-name', 'Ana')
    vi.advanceTimersByTime(200)
    app.type('f-name', 'Ana Popescu')
    vi.advanceTimersByTime(249)
    expect(app.$('mini-preview').textContent).not.toContain('Ana Popescu')
    vi.advanceTimersByTime(1)
    expect(app.$('mini-preview').textContent).toContain('Ana Popescu')
    expect(app.$('mini-empty').style.display).toBe('none')
  })
})
