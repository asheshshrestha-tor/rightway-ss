# Image brief

Every photograph the site needs, with a generation prompt, a size, and where
the file goes. **18 images in total**: 7 page heroes, 6 service images, 5 team
portraits.

Right now all of them are brand-toned SVG placeholders. Nothing is broken while
they stay — swap them in as you generate them, in any order.

---

## 1. Read this first

### Use the same style block on every prompt

Image models drift. Paste this **before** the per-image description so the whole
set looks like it came from one photographer on one day:

> Natural documentary photograph. Australian suburban Queensland setting.
> Warm, diffused daylight, no harsh shadows. Candid, unposed moment caught
> mid-action. Real, ordinary-looking people of varied ages and ethnicities.
> Muted natural colour palette with soft greens. Eye-level camera, 35mm lens,
> shallow depth of field. Photorealistic, high detail.

### And the same negative prompt

> staged studio portrait, posed smiling at camera, white seamless background,
> clinical or hospital setting, medical equipment, hospital gowns, text,
> watermark, logo, signage, distorted hands, extra fingers, oversaturated
> colours, HDR, lens flare, plastic skin, stock-photo feel

### The uniform

Support workers wear a **dark forest-green short-sleeve polo shirt**
(roughly `#166534`), with a small plain embroidered mark on the left chest.
Ask for *"a small plain embroidered emblem"* rather than a logo — models render
invented text badly. You can add the real logo afterwards if you want it
visible.

### Output settings

| | |
|---|---|
| Format | JPEG, quality 80–85 (or WebP if your host serves it) |
| Colour | sRGB |
| Target file size | Under 250 KB for heroes, under 150 KB for cards and portraits |
| Naming | Exactly as listed below — the filename is what the code looks for |

---

## 2. How to photograph disability well

This matters more than the technical settings. Rightway is a disability support
provider; the imagery is how a participant or a family member decides whether
this feels like a place that will treat them properly.

**Do**

- Show the person with disability **doing something** — cooking, choosing,
  travelling, laughing — not being done to.
- Put the support worker **alongside or below** eye level, never looming over
  or standing behind a seated person.
- Show a range of disability. Wheelchairs are the easy visual shorthand, but
  most disability is ambulatory, sensory, intellectual or invisible. Aim for
  roughly one wheelchair user across the whole set, not four.
- Reflect Toowoomba: multicultural, including Aboriginal and Torres Strait
  Islander people. Vary age, body type and gender.
- Keep settings ordinary and Australian — brick and weatherboard homes, gum
  trees and jacarandas, suburban kitchens, local parks.

**Don't**

- No pity framing (person looking sad, hand on shoulder, sympathetic head tilt).
- No "inspiration" framing (triumphant, backlit, gazing into the distance).
- No clinical settings. This is someone's home and community, not a ward.
- No shots that read as intrusive — personal care especially should be
  suggested with dignity, never intimate.

---

## 3. Page heroes — 7 images

These sit in the right-hand half of each hero band and are **masked into
organic shapes by CSS**. The mask eats into one side, so composition matters:

| Mask | Which pages | What gets cut |
|---|---|---|
| `leaf` | Home, About, Booking, Service detail, Vacancy detail | The **left edge** is cut by a large curve |
| `oval` | Services, NDIS Support | The **left half** is cut by a big ellipse — the most aggressive |
| `wide` | Careers, Vacancy detail | Only the left corners are rounded |
| `circle` | Privacy, Terms, Team profile | Everything outside a centred circle |

The CSS also uses `object-position: center 30%`, meaning **the top third of the
frame is favoured**. Put faces in the upper-middle and keep the subject
**right of centre** for `leaf` and `oval` images, or the mask will slice
through someone's face.

---

### `hero-home.svg` → `hero-home.jpg`

**Used on:** Home page hero, and the Book a Consultation page hero
**Size:** generate 1600×1200, export **1400×1050** (4:3) · mask: `leaf`
**Headline it sits beside:** "Supporting You to Live Life Your Way"

> A male support worker in his thirties wearing a dark forest-green polo shirt
> sits on a sofa beside an older woman in her seventies wearing a soft cream
> cardigan, in her own living room. They are mid-conversation and both
> genuinely laughing at something she has just said. She is doing the talking.
> Afternoon light through a large window, indoor plants, framed photos on a
> side table, a well-lived-in Australian home. Both figures sit right of
> centre in the frame with space to their left.

---

### `hero-about.svg` → `hero-about.jpg`

**Used on:** About page hero
**Size:** generate 1600×1200, export **1400×1050** (4:3) · mask: `leaf`
**Headline:** "About Rightway Support Services"

> A woman support worker in her late twenties in a dark forest-green polo walks
> alongside a young woman in her twenties who uses a manual wheelchair, moving
> together along a path in a suburban Queensland park. The young woman is
> leading the conversation and gesturing; the worker is listening and laughing.
> Dappled light through eucalyptus trees, dry green grass, mid-morning.
> Subjects right of centre, moving toward the camera.

---

### `hero-services.svg` → `hero-services.jpg`

**Used on:** Services listing page hero
**Size:** generate 1600×1200, export **1400×1050** (4:3) · mask: `oval` *(cuts hard on the left — keep the subject well right of centre)*
**Headline:** "Our Services — Support Tailored to You"

> A support worker in a dark forest-green polo crouches down to be at eye level
> with a man in his forties seated in a wheelchair, both looking at something
> the seated man is holding and discussing it. Outdoors in a park with large
> shade trees, warm late-afternoon light behind them. Relaxed, equal, two
> people working something out together. Composition weighted to the right
> third of the frame.

---

### `hero-ndis.svg` → `hero-ndis.jpg`

**Used on:** NDIS Support page hero
**Size:** generate 1600×1200, export **1400×1050** (4:3) · mask: `oval`
**Headline:** "NDIS Support — We're Here to Help"

> A woman support worker in a dark forest-green polo sits beside a woman in her
> fifties at a kitchen table in a bright suburban home, a folder and a laptop
> open between them. The participant is pointing at something on the page and
> asking a question; the worker is attentive. Natural window light, a mug of
> tea, ordinary kitchen clutter. Warm and practical, not clinical. Subjects
> right of centre.

---

### `hero-careers.svg` → `hero-careers.jpg`

**Used on:** Careers page hero, and every vacancy advert page
**Size:** generate 1800×1000, export **1600×900** (16:9) · mask: `wide`
**Headline:** "Careers — Make a Difference Every Day"

> A group of four support workers of mixed ages, genders and ethnicities, all
> in dark forest-green polo shirts, standing together outside a suburban
> Australian community centre. Relaxed and mid-laugh, arms loose, not lined up
> or posed. One is turned slightly toward another as if finishing a sentence.
> Bright overcast daylight. They fill the middle of a wide frame with room on
> both sides.

---

### `hero-privacy.svg` → `hero-privacy.jpg`

**Used on:** Privacy Policy page, Terms & Conditions page
**Size:** generate 1200×1200, export **1000×1000** (1:1) · mask: `circle` *(corners are lost — keep everything important centred)*
**Headline:** "Privacy Policy — Your Privacy Matters"

> A woman support worker in a dark forest-green polo sits beside an older man
> in his sixties in a bright living room, a document on the table between them.
> She is explaining something and he is nodding, clearly in charge of the
> decision. Calm, trusting, unhurried. Soft daylight from a window behind them.
> Both figures centred in a square frame, shot from the waist up.

---

### `faq-support.svg` → `faq-support.png`

**Used on:** FAQ page, beside the question list (desktop only - it is hidden
below 960px)
**Size:** generate 1200×1800, export **800×1200** (2:3 portrait)
**Format:** **PNG with a transparent background** - see below

How it renders: 265px wide, anchored to the **bottom** of its column with the
top corners rounded, sitting in front of a large pale-blue `?` positioned at
the **top-left**. So:

- Frame her **standing, cropped around mid-thigh**, so she reads as standing on
  the baseline rather than floating.
- Leave the **upper-left of the frame clear** - that is where the `?` shows.
- A cut-out beats a rectangular photo here: the `?` then shows *through* around
  the figure instead of being hidden behind a white box.

> A friendly woman support worker in her thirties wearing a dark forest-green
> short-sleeve polo shirt with a small plain embroidered emblem on the left
> chest. Standing three-quarter length, cropped at mid-thigh, body angled
> slightly toward camera, one hand resting lightly near her chin in a natural
> "happy to help" gesture. Warm, open, approachable expression, looking just
> past the lens. Even soft daylight from the front left. Isolated on a pure
> white background with clean edges, no cast shadow. Tall portrait frame with a
> little headroom above her.

Then remove the white background to make it a transparent PNG. If you would
rather keep it as a photograph, use the same prompt but ask for *"a plain, very
softly blurred pale background with no furniture, doorways or signage"* and
export as JPEG instead - it will still work, the `?` will simply sit behind the
photo rather than around her.

## 4. Service images — 6 images

**Where they appear:** the four cards on the Home page, the cards on the
Services listing, and the hero of each service's own page.

**Size for all:** generate 1800×1400, export **1200×900** (4:3)

Cards crop these to 4:3 with `object-fit: cover`, and the service detail hero
applies the `leaf` mask — so again, **keep the subject right of centre and in
the upper two-thirds.**

These five are **uploaded through the dashboard**, not saved as files:
**Website Content → Services → edit → Image**. No code change needed.

---

### `service-personal-care`

> A support worker in a dark forest-green polo stands beside a man in his
> sixties at a bedroom doorway, handing him a folded shirt as he gets ready for
> the day. He is standing under his own power with a walking stick. Warm
> morning light. Dignified and matter-of-fact — everyday help, nothing
> intimate or intrusive. Right of centre.

### `service-household-tasks`

> A support worker in a dark forest-green polo and a woman in her fifties
> preparing a meal together at a suburban kitchen bench, fresh vegetables on a
> board between them. The participant is doing the chopping; the worker is
> passing something across. Bright kitchen, natural light, comfortable clutter.

### `service-community-access`

> A support worker in a dark forest-green polo and a young man with Down
> syndrome sitting at an outdoor café table in a Queensland main street,
> drinks in front of them, mid-conversation and laughing. Ordinary Saturday
> morning, people passing in the soft-focus background.

### `service-home-shared-living`

> Two housemates in their thirties and a support worker in a dark forest-green
> polo relaxing together in the shared lounge room of a suburban house, one on
> the sofa, one in an armchair, all talking. Homely and lived-in — cushions,
> a bookshelf, a plant. Warm evening light.

### `service-transport`

> A support worker in a dark forest-green polo holding the passenger door of a
> small hatchback open while a woman in her forties gets in for an appointment,
> both mid-conversation. Suburban Queensland street with brick houses and a
> jacaranda tree. Bright, ordinary, unremarkable — the point is reliability.

### `service-placeholder` *(static file — save as `service-placeholder.jpg`)*

Shown automatically for any **new** service added in the dashboard before a
photo is uploaded, so keep it generic.

> A support worker in a dark forest-green polo and a participant sitting
> together at a table in a bright room, talking and looking at something
> between them. Deliberately non-specific — no visible task or equipment that
> ties it to one kind of support. Warm, calm, welcoming.

---

## 5. Team portraits — 5 images

**Where they appear:** the Meet Our Team grid on the About page (square cards),
and each person's own profile page (**cropped to a circle**).

**Size for all:** generate 1200×1200, export **800×800** (1:1 square)
**Framing:** head and shoulders, face centred, comfortable margin all round —
the circular crop on the profile page will trim the corners.

> ### Please use real photographs of the real people
>
> These four are named, real employees — Arshdeep Singh, Priya Kaur, Michael
> Brown and Sarah Wilson. Their profile pages list their actual qualifications
> and NDIS Worker Screening.
>
> A participant deciding who will come into their home is entitled to see who
> that person actually is. Putting a generated face under a real name with real
> credentials is misleading in exactly the situation where trust matters most,
> and it would be awkward to explain if anyone noticed.
>
> A phone camera against a plain wall in good window light is genuinely enough.
> Use the prompts below only as a **temporary stand-in**, or delete those
> members and add the real team through the dashboard when you have photos.

If you do need placeholders in the meantime, generate to this shared recipe and
vary only the person:

> Relaxed head-and-shoulders portrait of {PERSON}, wearing a dark forest-green
> polo shirt, standing against a plain, softly blurred neutral background.
> Warm natural window light from one side. Approachable half-smile, looking
> just past the camera. Square crop, face centred.

| File | Person | Vary this line |
|---|---|---|
| `team-arshdeep-singh` | Arshdeep Singh — Director | a Punjabi Australian man in his forties, short beard, calm and confident |
| `team-priya-kaur` | Priya Kaur — Operations Manager | a Punjabi Australian woman in her thirties, warm and organised |
| `team-michael-brown` | Michael Brown — Support Coordinator | an Anglo-Australian man in his fifties, glasses, thoughtful |
| `team-sarah-wilson` | Sarah Wilson — Team Leader | an Anglo-Australian woman in her forties, practical and friendly |

These four are **uploaded through the dashboard**:
**Website Content → Team → edit → Photo**.

### `team-placeholder` *(static file — save as `team-placeholder.jpg`)*

Shown for any **new** team member added before a photo is uploaded. Best as a
neutral graphic rather than a face — a soft brand-green tinted silhouette on a
pale background works better than an invented person.

---

## 6. Where each file goes

### Uploaded through the dashboard — no code change

| Images | Where |
|---|---|
| 5 service images | Website Content → Services → edit → **Image** |
| 4 team portraits | Website Content → Team → edit → **Photo** |

These land in `media/services/` and `media/team/` automatically.

### Saved as static files — needs a one-line template edit each

Drop the file into `static/images/`, then change the extension in the template
that references it (they currently say `.svg`):

| File | Template line to edit |
|---|---|
| `hero-home` | `templates/pages/home.html` and `templates/pages/consultation.html` |
| `hero-about` | `templates/pages/about.html` |
| `hero-services` | `templates/pages/services.html` |
| `hero-ndis` | `templates/pages/ndis_support.html` |
| `hero-careers` | `templates/pages/careers.html` and `templates/pages/vacancy_detail.html` |
| `hero-privacy` | `templates/pages/privacy_policy.html` and `templates/pages/terms.html` |
| `faq-support` | `templates/pages/faq.html` |
| `service-placeholder` | referenced from `pages/models.py` (`Service.image_url`) |
| `team-placeholder` | referenced from `pages/team_models.py` (`TeamMember.photo_url`) |

Tell me when you have the files and I'll do those edits and re-check every page.

### Alt text

Each `<img>` already carries descriptive alt text written for the placeholder.
Once the real photo is in, check the alt text still describes **that** picture —
`templates/pages/*.html`, search for `alt="`.

---

## 7. Quick checklist per image

- [ ] Subject right of centre (for `leaf` and `oval` heroes)
- [ ] Face in the upper two-thirds of the frame
- [ ] Nothing important in the corners (for `circle` crops)
- [ ] Polo shirt reads as dark forest green, not teal or olive
- [ ] No invented text or logos anywhere in the frame
- [ ] Hands look right — regenerate rather than accept a bad one
- [ ] Exported at the size in the table, under the file-size target
