/* Rightway Support Services - site behaviour
   - mobile navigation toggle
   - dropdown menus (hover on desktop, tap/click on touch + mobile)
   - FAQ accordion
*/
(function () {
    'use strict';

    document.documentElement.classList.add('js-ready');

    var DESKTOP = window.matchMedia('(min-width: 961px)');

    /* ------------------------------------------------------------ mobile nav */

    var toggle = document.querySelector('.nav-toggle');
    var nav = document.getElementById('primary-nav');

    function closeNav() {
        if (!nav || !toggle) return;
        nav.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
    }

    if (toggle && nav) {
        toggle.addEventListener('click', function () {
            var open = nav.classList.toggle('is-open');
            toggle.setAttribute('aria-expanded', String(open));
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

    /* --------------------------------------------------- sticky-header anchors */

    // Offset in-page jumps so the sticky header does not cover the target.
    function offsetForHeader() {
        if (!location.hash) return;
        var target = document.querySelector(location.hash);
        if (!target) return;
        var header = document.querySelector('.site-header');
        var offset = header ? header.offsetHeight + 16 : 0;
        window.scrollBy(0, -offset);
    }

    window.addEventListener('hashchange', offsetForHeader);
    window.addEventListener('load', function () {
        window.setTimeout(offsetForHeader, 0);
    });
})();
