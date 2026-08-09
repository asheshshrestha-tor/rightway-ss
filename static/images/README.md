# Image assets

## Logo

| File              | Notes                                                          |
| ----------------- | -------------------------------------------------------------- |
| `logo.png`        | Full-colour logo, background removed from `Docs/logo.png`       |
| `logo-light.png`  | White treatment, used on the navy footer                        |
| `logo-mark.png`   | Square roundel only                                             |
| `favicon-32.png`  | Browser tab icon                                                |
| `favicon-180.png` | Apple touch icon                                                |

The supplied `Docs/logo.png` is fully opaque - its "transparent" checkerboard is
baked-in pixels. These files have it removed.

## Photography placeholders

Every `.svg` here stands in for a photograph from the design mockup. They are
brand-toned abstract fills, not final artwork.

| File                              | Where it appears           | Suggested size |
| --------------------------------- | -------------------------- | -------------- |
| `hero-home.svg`                   | Home hero                  | 1200 x 900     |
| `hero-about.svg`                  | About hero                 | 1200 x 900     |
| `hero-services.svg`               | Services hero              | 1200 x 900     |
| `hero-ndis.svg`                   | NDIS Support hero          | 1200 x 900     |
| `hero-careers.svg`                | Careers hero               | 1400 x 800     |
| `hero-privacy.svg`                | Privacy & Terms portrait   | 1000 x 1000    |
| `service-personal-care.svg`       | Service card               | 900 x 700      |
| `service-household-tasks.svg`     | Service card               | 900 x 700      |
| `service-community-access.svg`    | Service card               | 900 x 700      |
| `service-home-shared-living.svg`  | Service card               | 900 x 700      |
| `team-arshdeep-singh.svg`         | About - team               | 600 x 600      |
| `team-priya-kaur.svg`             | About - team               | 600 x 600      |
| `team-michael-brown.svg`          | About - team               | 600 x 600      |
| `team-sarah-wilson.svg`           | About - team               | 600 x 600      |
| `faq-support.svg`                 | FAQ aside                  | 800 x 1000     |

To swap one for a real photo, add the image here and update the extension:

- hero and FAQ images: in the matching template under `templates/pages/`
- service and team images: in `SERVICES` / `TEAM` in `pages/content.py`

All of them are rendered with `object-fit: cover`, so exact dimensions do not
matter as long as the aspect ratio is close.
