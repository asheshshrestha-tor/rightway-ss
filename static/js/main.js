/* Rightway Support Services - site behaviour
   - mobile navigation toggle
   - dropdown menus (hover on desktop, tap/click on touch + mobile)
   - FAQ accordion
   - collapsing utility bar in the header
*/
(function () {
    'use strict';

    document.documentElement.classList.add('js-ready');

    var DESKTOP = window.matchMedia('(min-width: 961px)');
    var header = document.querySelector('.site-header');

    /* ------------------------------------------------------------ mobile nav */

    var toggle = document.querySelector('.nav-toggle');
    var nav = document.getElementById('primary-nav');

    function closeNav() {
        if (!nav || !toggle) return;
        nav.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
        // Scrolling with the menu open leaves the topbar frozen - see
        // applyScrollState - so catch it up once the menu is out of the way.
        applyScrollState();
    }

    if (toggle && nav) {
        // Closing goes through closeNav rather than a plain toggle, so the
        // topbar it was holding open gets its catch-up call.
        toggle.addEventListener('click', function () {
            if (nav.classList.contains('is-open')) {
                closeNav();
                return;
            }
            nav.classList.add('is-open');
            toggle.setAttribute('aria-expanded', 'true');
        });
    }

    /* ------------------------------------------------------------- dropdowns */

    var dropdowns = Array.prototype.slice.call(
        document.querySelectorAll('.nav-item--has-menu')
    );

    function closeDropdowns(except) {
        dropdowns.forEach(function (item) {
            if (item === except) return;
            item.classList.remove('is-open');
            var trigger = item.querySelector(':scope > a');
            if (trigger) trigger.setAttribute('aria-expanded', 'false');
        });
    }

    dropdowns.forEach(function (item) {
        var trigger = item.querySelector(':scope > a');
        if (!trigger) return;

        // Desktop: open on hover/focus. Mobile: the link's first tap opens the
        // submenu, the second follows through to the section page.
        item.addEventListener('mouseenter', function () {
            if (!DESKTOP.matches) return;
            closeDropdowns(item);
            item.classList.add('is-open');
            trigger.setAttribute('aria-expanded', 'true');
        });

        item.addEventListener('mouseleave', function () {
            if (!DESKTOP.matches) return;
            item.classList.remove('is-open');
            trigger.setAttribute('aria-expanded', 'false');
        });

        trigger.addEventListener('click', function (event) {
            if (DESKTOP.matches) return;
            if (!item.classList.contains('is-open')) {
                event.preventDefault();
                closeDropdowns(item);
                item.classList.add('is-open');
                trigger.setAttribute('aria-expanded', 'true');
            }
        });

        item.addEventListener('focusin', function () {
            if (!DESKTOP.matches) return;
            closeDropdowns(item);
            item.classList.add('is-open');
            trigger.setAttribute('aria-expanded', 'true');
        });

        item.addEventListener('focusout', function (event) {
            if (!DESKTOP.matches) return;
            if (item.contains(event.relatedTarget)) return;
            item.classList.remove('is-open');
            trigger.setAttribute('aria-expanded', 'false');
        });
    });

    document.addEventListener('click', function (event) {
        if (event.target.closest('.site-header')) return;
        closeDropdowns(null);
        closeNav();
    });

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape') return;
        closeDropdowns(null);
        closeNav();
    });

    // Following an in-page link from the mobile menu should close it.
    if (nav) {
        nav.addEventListener('click', function (event) {
            var link = event.target.closest('a');
            if (!link || DESKTOP.matches) return;
            if (link.parentElement.parentElement.classList.contains('nav-menu') ||
                !link.closest('.nav-item--has-menu')) {
                closeNav();
            }
        });
    }

    /* ---------------------------------------------------------- faq accordion */

    var faqList = document.querySelector('[data-faq]');

    if (faqList) {
        faqList.addEventListener('click', function (event) {
            var button = event.target.closest('.faq-question');
            if (!button) return;

            var item = button.closest('.faq-item');
            var isOpen = item.classList.contains('is-open');

            faqList.querySelectorAll('.faq-item.is-open').forEach(function (open) {
                open.classList.remove('is-open');
                open.querySelector('.faq-question').setAttribute('aria-expanded', 'false');
            });

            if (!isOpen) {
                item.classList.add('is-open');
                button.setAttribute('aria-expanded', 'true');
            }
        });
    }

    /* ------------------------------------------------------ collapsing topbar */

    // The utility bar (phone, email, address, hours) is only worth its height
    // while someone is still deciding whether to get in touch. Once they start
    // reading it folds away, leaving a slimmer sticky nav, and it comes back
    // when they return to the top of the page.
    //
    // Two thresholds rather than one: collapsing and expanding at the same
    // point would let the header flip back and forth around that scroll
    // position, and collapsing shortens the document, which can nudge the
    // scroll position back over the line on its own.
    var topbar = header ? header.querySelector('.topbar') : null;
    var COLLAPSE_BELOW = 90;   // scrolled this far down: fold the bar away
    var EXPAND_ABOVE = 8;      // back at the very top: bring it back
    var condensed = false;
    var scrollQueued = false;

    function applyScrollState() {
        scrollQueued = false;
        if (!header || !topbar) return;

        // Holding the bar open while the mobile menu is down: the menu hangs
        // off the bottom of the header, so resizing it mid-scroll drags the
        // open menu up the screen.
        if (nav && nav.classList.contains('is-open')) return;

        var y = window.pageYOffset || document.documentElement.scrollTop;
        var next = condensed ? y > EXPAND_ABOVE : y > COLLAPSE_BELOW;
        if (next === condensed) return;

        condensed = next;
        header.classList.toggle('is-condensed', condensed);
    }

    function onScroll() {
        if (scrollQueued) return;
        scrollQueued = true;
        window.requestAnimationFrame(applyScrollState);
    }

    if (header && topbar) {
        window.addEventListener('scroll', onScroll, { passive: true });
        // Reloading or coming back through history restores the old scroll
        // position, so the bar has to start in the state that matches it.
        applyScrollState();
    }

    /* --------------------------------------------------- sticky-header anchors */

    // Nothing to do here any more: `scroll-margin-top` in style.css keeps
    // in-page jumps clear of the header. It used to be a scrollBy() correction
    // fired after load, which cancelled the browser's own smooth scroll to the
    // fragment and left the link doing nothing at all.
})();
