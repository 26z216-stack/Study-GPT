"""Record a captioned demo video and a screenshot PDF of StudyGPT (real app, real AI calls).

    pip install playwright imageio-ffmpeg        # recording tools only, not app deps
    python -m playwright install ffmpeg
    python scripts/record_demo.py                # -> docs/demo/studygpt-demo.mp4 + studygpt-screenshots.pdf

Runs its own server on a throwaway database, signs up the test account below,
and drives Edge through the full flow. Needs GEMINI_API_KEY in .env.
"""
import base64
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'demo' / 'studygpt-demo.mp4'
PDF = ROOT / 'docs' / 'demo' / 'studygpt-screenshots.pdf'
PORT = 5055
BASE = f'http://127.0.0.1:{PORT}'
SHOTS = []   # (title, description, png bytes) captured during the run

# Test account created inside the throwaway demo database.
NAME, EMAIL, PASSWORD = 'Arjun', 'arjun@studygpt.app', 'studygpt123'

PHYSICS_SYLLABUS = """Unit 1: Kinematics - motion in 1D and 2D, projectile motion, relative velocity
Unit 2: Laws of motion - Newton's laws, friction, circular motion
Unit 3: Work, energy and power - work-energy theorem, conservation of energy, collisions
Unit 4: Rotational motion - torque, moment of inertia, angular momentum
Unit 5: Gravitation - Kepler's laws, gravitational potential, satellites"""

MATHS_SYLLABUS = """Limits and continuity; Differentiation rules; Applications of derivatives (maxima, minima, rate of change);
Integration techniques; Definite integrals and area; Differential equations"""

ROUTINE = ("College 9am to 4pm Monday to Friday, bus home takes an hour. Gym 6-7pm on Mon, Wed, Fri. "
           "I focus best in the mornings. Saturday free after 11am, Sunday family lunch 12-3. I sleep by 11pm.")

FEYNMAN = ("Kinematics is about describing how things move without worrying about why. We use position, velocity "
           "and acceleration. Velocity is how fast position changes and acceleration is how fast velocity changes. "
           "For a ball thrown at an angle, the sideways speed stays the same while gravity keeps pulling it down, "
           "so it follows a curved path called a parabola.")

CAPTION_JS = """
(() => {
  const draw = () => {
    const text = sessionStorage.getItem('demo-cap');
    let el = document.getElementById('demo-cap');
    if (!text) { if (el) el.remove(); return; }
    if (!el) {
      el = document.createElement('div');
      el.id = 'demo-cap';
      el.style.cssText = 'position:fixed;left:50%;bottom:26px;transform:translateX(-50%);z-index:99999;' +
        'background:rgba(20,16,40,.92);color:#fff;padding:12px 22px;border-radius:14px;font:600 19px/1.35 ' +
        '"Plus Jakarta Sans",system-ui,sans-serif;max-width:86%;text-align:center;box-shadow:0 8px 30px rgba(0,0,0,.35);' +
        'border:1px solid rgba(139,126,255,.6);pointer-events:none';
      document.documentElement.appendChild(el);
    }
    el.textContent = text;
  };
  window.__demoCap = draw;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', draw); else draw();
})();
"""

CARD_JS = """([title, sub]) => {
  const d = document.createElement('div');
  d.id = 'demo-card';
  d.style.cssText = 'position:fixed;inset:0;z-index:100000;display:grid;place-items:center;text-align:center;' +
    'background:linear-gradient(135deg,#1b1640,#5B4BDB);color:#fff;font-family:"Plus Jakarta Sans",system-ui,sans-serif';
  d.innerHTML = '<div><div style="width:84px;height:84px;border-radius:22px;background:#fff;color:#5B4BDB;display:grid;' +
    'place-items:center;font-size:44px;font-weight:800;margin:0 auto 22px">S</div>' +
    '<div style="font-size:58px;font-weight:800;letter-spacing:-.02em">' + title + '</div>' +
    '<div style="font-size:24px;opacity:.85;margin-top:12px;max-width:900px">' + sub + '</div></div>';
  document.documentElement.appendChild(d);
}"""


def wait_for_server():
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + '/login', timeout=1)
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError('demo server did not start')


def main():
    tmp = Path(tempfile.mkdtemp(prefix='studygpt-demo-'))
    env = dict(os.environ, DATABASE_URL='sqlite:///' + (tmp / 'demo.db').as_posix(), PORT=str(PORT),
               FLASK_DEBUG='false')
    server = subprocess.Popen([sys.executable, 'start.py'], cwd=ROOT, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for_server()
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=True)
            ctx = browser.new_context(viewport={'width': 1280, 'height': 720}, color_scheme='light',
                                      record_video_dir=str(tmp), record_video_size={'width': 1280, 'height': 720})
            ctx.add_init_script(CAPTION_JS)
            ctx.set_default_timeout(90_000)
            page = ctx.new_page()
            page.on('dialog', lambda d: d.accept())
            run(page)
            video = page.video.path()
            ctx.close()
            browser.close()
        encode(video)
        build_pdf()
    finally:
        server.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


def run(page):
    def cap(text):
        page.evaluate('t => { t ? sessionStorage.setItem("demo-cap", t) : sessionStorage.removeItem("demo-cap"); '
                      'window.__demoCap && window.__demoCap(); }', text)

    def pause(s):
        page.wait_for_timeout(int(s * 1000))

    def shot(title, text):
        SHOTS.append((title, text, page.screenshot(type='png')))

    def card(title, sub, secs):
        page.evaluate(CARD_JS, [title, sub])
        pause(secs)
        page.evaluate('document.getElementById("demo-card").remove()')

    def slow(selector, text, delay=18):
        page.locator(selector).click()
        page.locator(selector).press_sequentially(text, delay=delay)

    def go(path):
        page.goto(BASE + path)
        page.wait_for_load_state('networkidle')

    def scroll_to(selector):
        page.locator(selector).first.scroll_into_view_if_needed()

    # ── Intro + sign up ──────────────────────────────────────────────
    go('/signup')
    card('StudyGPT', 'AI-powered study planner: personalised schedules from your exam dates, subjects and free time', 4)
    cap('Create an account')
    slow('#name', NAME, 60)
    slow('#email', EMAIL, 30)
    slow('#password', PASSWORD, 30)
    pause(0.5)
    shot('Sign up', 'Students create an account with a name, email and password.')
    page.get_by_role('button', name='Create account').click()
    page.wait_for_load_state('networkidle')

    # ── Subjects ─────────────────────────────────────────────────────
    cap('Add subjects with exam date, difficulty and priority')
    pause(1.5)
    slow('#name', 'Physics', 60)
    page.fill('input[name=exam_date] >> nth=-1', (date.today() + timedelta(days=6)).isoformat())
    page.select_option('select[name=difficulty] >> nth=-1', '4')
    page.select_option('select[name=priority] >> nth=-1', '5')
    pause(1)
    shot('Subjects, exam dates, difficulty and priority',
         'Each subject gets an exam date, a difficulty (1-5) and a priority (1-5). These feed directly into the scheduler.')
    page.get_by_role('button', name='Add subject').click()
    page.wait_for_load_state('networkidle')

    # ── AI syllabus import ───────────────────────────────────────────
    cap('Paste the syllabus: AI splits it into topics with difficulty and hours')
    page.locator('textarea[name=syllabus]').fill(PHYSICS_SYLLABUS)
    pause(2)
    page.get_by_role('button', name='Generate topics').click()
    cap('AI is reading the syllabus…')
    page.wait_for_url('**/subjects/*', wait_until='networkidle')
    cap('Topics created, each with an AI-estimated difficulty and study time')
    pause(1)
    shot('AI syllabus import and syllabus tracker',
         'Paste the syllabus and the AI splits it into study topics, each with a difficulty and an estimated number '
         'of hours. Status and confidence are tracked per topic.')
    pause(3.5)

    cap('Add as many subjects as you need')
    go('/subjects')
    page.fill('#name', 'Mathematics')
    page.fill('input[name=exam_date] >> nth=-1', (date.today() + timedelta(days=11)).isoformat())
    page.select_option('select[name=priority] >> nth=-1', '4')
    pause(1)
    page.get_by_role('button', name='Add subject').click()
    page.wait_for_load_state('networkidle')
    page.locator('textarea[name=syllabus]').fill(MATHS_SYLLABUS)
    page.get_by_role('button', name='Generate topics').click()
    page.wait_for_url('**/subjects/*', wait_until='networkidle')
    pause(2.5)

    # ── AI routine → timed timetable ─────────────────────────────────
    go('/subjects')
    scroll_to('textarea[name=routine]')
    cap('Describe your week in plain English: AI finds your free study slots')
    slow('textarea[name=routine]', ROUTINE, 8)
    pause(1)
    shot('Describe your routine in plain English',
         "The AI reads the student's weekly routine (classes, commute, gym, sleep, preferences) and works out "
         'their free study windows for every day.')
    page.get_by_role('button', name='Build my schedule').click()
    cap('Building your schedule…')
    page.wait_for_url('**/timetable', wait_until='networkidle')
    cap('Your personalised timetable, with real clock times inside your free slots')
    pause(1)
    shot('Personalised timetable',
         'The scheduler fills each free window with 30-60 minute blocks, putting urgent, difficult and '
         'low-confidence topics first and interleaving subjects. Every session has a real start and end time.')
    pause(4)
    cap('Urgent, difficult and weak topics come first, and subjects are interleaved')
    page.mouse.wheel(0, 300)
    pause(4)
    page.get_by_role('link', name='→').click()
    page.wait_for_load_state('networkidle')
    cap('Next week: the day before each exam gets a revision block, and exam days are flagged')
    pause(1)
    shot('Exam-eve revision',
         "The day before each exam gets a revision block on that subject's weakest topic. Nothing is scheduled "
         'for a subject on or after its exam day.')
    pause(4)

    # ── Dashboard + auto-rescheduling ────────────────────────────────
    go('/')
    cap("Today: your sessions, exam countdowns and readiness at a glance")
    pause(1)
    shot('Today dashboard',
         "Today's timed sessions with Focus, Learn, Done and Skip actions, plus exam readiness, exam countdowns, "
         'due flashcards and weak topics.')
    pause(3.5)
    skip = page.locator('button[title="Can\'t do it today, move it"]')
    if skip.count():
        cap("Can't make a session? Skip it, and StudyGPT reschedules the work automatically")
        pause(2)
        skip.first.click()
        page.wait_for_load_state('networkidle')
        pause(1)
        shot('Automatic rescheduling',
             'Skipping or missing a session marks it missed and regenerates the plan from today, so the work '
             'moves into upcoming free slots automatically.')
        pause(3.5)

    # ── AI quiz ──────────────────────────────────────────────────────
    go('/subjects/1')
    page.get_by_role('link', name='Learn').first.click()
    page.wait_for_load_state('networkidle')
    cap('Every topic has an AI quiz, flashcards and the Feynman Technique')
    pause(2.5)
    page.get_by_role('button', name='Generate quiz').click()
    cap('AI quiz: 5 fresh questions on this topic')
    page.wait_for_selector('.q')
    pause(2)
    for i, q in enumerate(page.locator('.q').all()):
        q.scroll_into_view_if_needed()
        q.locator('.opt').nth([1, 0, 2, 1, 0][i % 5]).click()
        pause(0.8)
    page.locator('#quiz-submit').click()
    page.wait_for_selector('#quiz-score .flash')
    scroll_to('#quiz-score')
    cap('Your score updates the topic confidence, and the timetable re-prioritises itself')
    pause(1)
    shot('AI quiz generator',
         "Five AI-written multiple-choice questions per topic, with explanations. The score updates the topic's "
         'confidence, which re-prioritises the timetable.')
    pause(4.5)

    # ── Feynman ──────────────────────────────────────────────────────
    page.mouse.wheel(0, -3000)
    page.locator('.tab[data-tab=feynman]').click()
    cap("Feynman Technique: explain it simply, and AI finds the gaps in your understanding")
    slow('#feyn-text', FEYNMAN, 6)
    pause(1)
    page.locator('#feyn-go').click()
    page.wait_for_selector('#feyn-result .fb h3')
    pause(2.5)
    page.locator('#feyn-result').scroll_into_view_if_needed()
    page.mouse.wheel(0, 250)
    cap('Strengths, gaps, misconceptions, jargon, an analogy and a score')
    pause(1)
    shot('Feynman Technique',
         'The student explains the topic in simple words. The AI returns strengths, gaps, misconceptions, '
         'unexplained jargon, a helpful analogy and a score.')
    pause(5)

    # ── Flashcards + spaced repetition ───────────────────────────────
    page.mouse.wheel(0, -3000)
    page.locator('.tab[data-tab=cards]').click()
    cap('AI flashcards, scheduled with spaced repetition')
    pause(1)
    with page.expect_response(lambda r: r.url.endswith('/flashcards') and r.request.method == 'POST') as resp:
        page.locator('#cards-gen').click()
    page.wait_for_load_state('networkidle')
    cards_ok = resp.value.ok
    pause(1.5)
    shot('AI flashcards',
         'Generate a set of flashcards for any topic, or write your own. Every card is scheduled with the SM-2 '
         'spaced repetition algorithm.')
    pause(1.5)
    go('/review')
    cap('Review due cards: Again, Hard, Good or Easy decides when each card comes back')
    for i, grade in enumerate(['Good', 'Easy', 'Hard'] if page.locator('#card').count() else []):
        pause(1.8)
        page.locator('#card').click()
        pause(2.2)
        if i == 0:
            shot('Spaced repetition review',
                 'Flip a card, then grade it Again, Hard, Good or Easy. SM-2 decides when the card comes back: '
                 'known cards less often, missed cards sooner.')
        page.get_by_role('button', name=grade).click()
    pause(1.5)

    # ── Report ───────────────────────────────────────────────────────
    go('/report')
    cap('Exam readiness report: coverage, confidence, hours studied and plan adherence')
    pause(3.5)
    page.locator('#ai-btn').click()
    page.wait_for_selector('#ai-box h2')
    cap('AI analysis: what to focus on over the next 3 days')
    pause(1)
    shot('Exam readiness report',
         'Readiness per subject (40% syllabus coverage + 60% measured confidence), hours studied, plan '
         'adherence, and an AI analysis of what to focus on next.')
    pause(5)

    # ── Coach ────────────────────────────────────────────────────────
    go('/coach')
    cap('AI study coach: it knows your subjects, exams, timetable and weak spots')
    pause(1.5)
    page.locator('.chip').first.click()
    page.wait_for_function("() => { const m = [...document.querySelectorAll('.msg.coach')].pop(); "
                           "return m && m.textContent.trim() !== '…'; }")
    pause(1)
    shot('AI study coach',
         "A chatbot that sees the student's real subjects, exam dates, timetable and weak topics, and gives "
         'specific advice.')
    pause(6)

    # ── Focus timer + theme ──────────────────────────────────────────
    go('/')
    page.get_by_role('link', name='⏱️ Focus').first.click()
    page.wait_for_load_state('networkidle')
    cap('Focus timer linked to your planned session')
    page.locator('#start').click()
    pause(2)
    shot('Focus timer', 'A Pomodoro / deep-work timer linked to the planned session. It keeps running across '
                        'page reloads.')
    pause(2)
    go('/')
    cap('Light and dark themes')
    page.locator('#theme-toggle').click()
    pause(1)
    shot('Light and dark themes',
         'Light and dark themes, a daily motivational quote, and a mobile layout with bottom navigation.')
    pause(2)
    cap('')
    card('StudyGPT', 'Plan smarter · Adapt automatically · Learn actively<br><br>'
                     '<span style="font-size:20px">github.com/26z216-stack/Study-GPT</span>', 4.5)


def encode(webm):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error', '-i', str(webm),
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '26', '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart', str(OUT)], check=True)
    print(f'Saved {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)')


def build_pdf():
    """Screenshots + descriptions -> one feature per landscape A4 page."""
    sections = ''.join(
        f'<section><h2><span>{i:02d}</span>{title}</h2><p>{text}</p>'
        f'<img src="data:image/png;base64,{base64.b64encode(png).decode()}"></section>'
        for i, (title, text, png) in enumerate(SHOTS, 1))
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
      body {{ font-family: "Segoe UI", system-ui, sans-serif; color: #1C1B22; margin: 0; }}
      section {{ page-break-after: always; }}
      section:last-child {{ page-break-after: auto; }}
      .cover {{ height: 178mm; display: flex; flex-direction: column; justify-content: center; align-items: center;
                text-align: center; background: linear-gradient(135deg, #1b1640, #5B4BDB); color: #fff; border-radius: 14px; }}
      .cover h1 {{ font-size: 54px; margin: 0 0 10px; }}
      .cover p {{ font-size: 20px; opacity: .9; max-width: 760px; margin: 4px; }}
      h2 {{ font-size: 22px; margin: 0 0 4px; display: flex; gap: 12px; align-items: center; }}
      h2 span {{ background: #5B4BDB; color: #fff; border-radius: 8px; padding: 2px 10px; font-size: 16px; }}
      p {{ font-size: 14px; color: #555; margin: 0 0 10px; }}
      img {{ display: block; width: auto; max-width: 100%; max-height: 152mm; margin: 0 auto;
             border: 1px solid #ddd; border-radius: 10px; }}
    </style></head><body>
      <section class="cover"><h1>StudyGPT</h1>
        <p>AI-powered study planner: personalised study schedules from exam dates, subjects and available time</p>
        <p style="margin-top:22px;font-size:15px">github.com/26z216-stack/Study-GPT</p></section>
      {sections}</body></html>"""
    PDF.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page()
        page.set_content(html, wait_until='load')
        page.pdf(path=str(PDF), format='A4', landscape=True, print_background=True,
                 margin={'top': '12mm', 'bottom': '12mm', 'left': '14mm', 'right': '14mm'})
        browser.close()
    print(f'Saved {PDF} ({len(SHOTS)} screenshots, {PDF.stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
