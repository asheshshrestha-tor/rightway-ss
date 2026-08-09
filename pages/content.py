"""Static site content for the public pages.

Kept in one module so copy can be edited without touching templates, and so the
same data can later be swapped for database-backed models without changing the
templates that consume it.
"""

# Site name, contact details, logo, favicon, footer copy, map and social
# links now live in the database (pages.models.SiteSettings / SocialLink)
# so staff can edit them from the dashboard. See migration
# pages/0011_seed_site_settings.py for the original hardcoded values.

# Services now live in the database (pages.models.Service) so staff can edit
# them from the dashboard. See migration pages/0004_seed_services.py for the
# original hardcoded content.

# ----------------------------------------------------- trust / value props

WHY_US = [
    {
        "icon": "person-heart",
        "title": "Person Centred",
        "text": "Support tailored to your needs.",
    },
    {
        "icon": "hands-heart",
        "title": "Experienced",
        "text": "Qualified and caring professionals.",
    },
    {
        "icon": "shield-check",
        "title": "Trusted",
        "text": "Reliable and transparent.",
    },
    {
        "icon": "community",
        "title": "Local & Community",
        "text": "Proudly supporting our local community.",
    },
]

SERVICE_PROMISES = [
    {
        "icon": "person-heart",
        "title": "Person Centred",
        "text": "Support tailored to your needs.",
    },
    {
        "icon": "calendar-check",
        "title": "Flexible",
        "text": "Services that adapt to your goals.",
    },
    {
        "icon": "hands-heart",
        "title": "Experienced",
        "text": "Qualified and caring professionals.",
    },
    {
        "icon": "hand-heart",
        "title": "Local & Trusted",
        "text": "Proudly supporting our community.",
    },
]

VALUES = [
    {"icon": "leaf-heart", "title": "Respect"},
    {"icon": "shield-check", "title": "Integrity"},
    {"icon": "star", "title": "Inclusion"},
    {"icon": "sprout", "title": "Empowerment"},
    {"icon": "heart", "title": "Compassion"},
]

# Team members now live in the database (pages.models.TeamMember) so staff
# can edit them from the dashboard. See migration pages/0009_seed_team.py
# for the original hardcoded content.

# ------------------------------------------------------------ NDIS page

NDIS_HIGHLIGHTS = [
    "Plan management support",
    "Support coordination",
    "Capacity building",
    "Personalised services",
]

NDIS_STEPS = [
    {
        "icon": "check-badge",
        "title": "Understand Your Goals",
        "text": "We listen and understand your goals and needs.",
    },
    {
        "icon": "plan",
        "title": "Plan & Coordinate",
        "text": "We help plan and coordinate the right support.",
    },
    {
        "icon": "clipboard",
        "title": "Deliver Support",
        "text": "Our team delivers high-quality support services.",
    },
    {
        "icon": "refresh",
        "title": "Review & Improve",
        "text": "We regularly review to ensure your goals are met.",
    },
]

NDIS_SERVICES = [
    "Daily personal activities",
    "Household tasks",
    "Transport",
    "Community access",
    "Life skills development",
    "Home & shared living",
]

# ------------------------------------------------------------ Careers page

CAREER_BENEFITS = [
    {
        "icon": "person-heart",
        "title": "Meaningful Work",
        "text": "Make a positive impact every day.",
    },
    {
        "icon": "hands-heart",
        "title": "Supportive Team",
        "text": "Work with a friendly and supportive team.",
    },
    {
        "icon": "growth",
        "title": "Growth Opportunities",
        "text": "Training and career development.",
    },
    {
        "icon": "clock-flex",
        "title": "Flexible Work",
        "text": "We offer flexible hours to suit you.",
    },
]

VACANCIES = [
    {
        "title": "Support Worker",
        "detail": "Casual & part-time · Toowoomba and surrounds",
    },
    {
        "title": "Support Coordinator",
        "detail": "Full-time · Toowoomba, QLD",
    },
    {
        "title": "Community Access Worker",
        "detail": "Casual · Toowoomba and surrounds",
    },
    {
        "title": "Admin Assistant",
        "detail": "Part-time · Toowoomba, QLD",
    },
]

# ---------------------------------------------------------------- FAQ page

FAQS = [
    {
        "question": "What is NDIS?",
        "answer": (
            "The National Disability Insurance Scheme (NDIS) is the Australian "
            "Government's way of funding reasonable and necessary support for "
            "people with permanent and significant disability. Your NDIS plan "
            "sets out your goals and the funded support that helps you reach "
            "them."
        ),
    },
    {
        "question": "How do I access your services?",
        "answer": (
            "Book a free, no-obligation consultation through our booking page, "
            "or give us a call. We will talk through your goals "
            "and NDIS plan, then match you with support workers who suit your "
            "needs and schedule."
        ),
    },
    {
        "question": "Do you provide support outside Toowoomba?",
        "answer": (
            "Yes. We are based in Toowoomba and also deliver support across the "
            "surrounding areas. Contact us with your location and we will "
            "confirm availability in your area."
        ),
    },
    {
        "question": "How are your support workers trained?",
        "answer": (
            "All of our support workers hold the relevant qualifications, NDIS "
            "Worker Screening and first aid certification. They complete our "
            "induction program and ongoing training in person-centred practice, "
            "manual handling and safeguarding."
        ),
    },
    {
        "question": "Can I choose my support worker?",
        "answer": (
            "Absolutely. Choice and control are central to how we work. We "
            "introduce you to workers we believe are a good match, and you are "
            "welcome to request a change at any time."
        ),
    },
    {
        "question": "How do I book a free consultation?",
        "answer": (
            "Use the booking form on our Book a Consultation page - tell us when "
            "suits you and whether you would prefer we visit your home or talk "
            "over the phone. We will respond within one business day to confirm "
            "a time. You are welcome to call us instead if that is easier."
        ),
    },
    {
        "question": "What are your office hours?",
        "answer": (
            "Our office is open Monday to Friday, 8:00 AM to 5:00 PM. Support "
            "services can be arranged outside these hours by agreement, "
            "including evenings and weekends."
        ),
    },
    {
        "question": "How do you ensure my safety?",
        "answer": (
            "Every worker is screened, trained and supervised. We complete a "
            "risk assessment before support begins, keep clear incident and "
            "feedback processes, and review your support regularly so it stays "
            "safe and right for you."
        ),
    },
]

# ------------------------------------------------------- Privacy policy page

PRIVACY_SECTIONS = [
    {
        "title": "Information We Collect",
        "body": (
            "We collect personal information that is necessary to provide our "
            "services to you. This may include your name, contact details, NDIS "
            "participant number, support needs, health information relevant to "
            "your care, and records of the support we deliver."
        ),
    },
    {
        "title": "How We Use Information",
        "body": (
            "We use your information to provide and improve our services and "
            "communicate with you. This includes coordinating your support, "
            "matching you with suitable workers, meeting our reporting "
            "obligations as a registered NDIS provider, and responding to your "
            "enquiries."
        ),
    },
    {
        "title": "Information Sharing",
        "body": (
            "We do not share your personal information with third parties "
            "without your consent, except where required or permitted by law, "
            "or where sharing is necessary to protect your safety or the safety "
            "of others."
        ),
    },
    {
        "title": "Your Rights",
        "body": (
            "You have the right to access, update or request the deletion of "
            "your personal information. You may also ask us how your "
            "information is stored, or make a complaint about how it has been "
            "handled. We will respond within a reasonable time."
        ),
    },
    {
        "title": "Contact Us",
        "body": (
            "If you have any questions about this policy, please contact us. We "
            "are happy to explain how your information is handled and to work "
            "with you to resolve any concerns."
        ),
    },
]

TERMS_SECTIONS = [
    {
        "title": "Using This Website",
        "body": (
            "The content on this website is provided for general information "
            "about our services. While we take care to keep it accurate and up "
            "to date, it is not a substitute for individual advice about your "
            "own situation or NDIS plan."
        ),
    },
    {
        "title": "Service Agreements",
        "body": (
            "Support is delivered under a written service agreement between you "
            "and Rightway Support Services. That agreement sets out the support "
            "to be provided, the fees, cancellation terms and how either party "
            "may end the arrangement."
        ),
    },
    {
        "title": "Fees and Cancellations",
        "body": (
            "Fees are charged in line with the current NDIS Pricing "
            "Arrangements and Price Limits. Cancellation terms are set out in "
            "your service agreement and follow the NDIS short notice "
            "cancellation rules."
        ),
    },
    {
        "title": "Feedback and Complaints",
        "body": (
            "We welcome feedback and take complaints seriously. Contact us "
            "directly and we will acknowledge your complaint promptly. You may "
            "also contact the NDIS Quality and Safeguards Commission at any "
            "time."
        ),
    },
    {
        "title": "Changes to These Terms",
        "body": (
            "We may update these terms from time to time. The current version "
            "is always available on this page, and material changes affecting "
            "existing participants will be communicated directly."
        ),
    },
]
