<template>
  <div class="min-h-screen bg-stone-50 text-zinc-950 transition-colors duration-300 dark:bg-zinc-950 dark:text-zinc-100">
    <div class="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden="true">
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(251,191,36,0.14),transparent_32%)] dark:bg-[radial-gradient(circle_at_top_left,rgba(251,191,36,0.08),transparent_32%)]" />
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_85%_10%,rgba(45,212,191,0.12),transparent_28%)] dark:bg-[radial-gradient(circle_at_85%_10%,rgba(45,212,191,0.08),transparent_28%)]" />
      <div class="absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.82),rgba(245,245,244,0.92))] dark:bg-[linear-gradient(180deg,rgba(9,9,11,0.8),rgba(9,9,11,0.97))]" />
    </div>

    <LandingNavbar />

    <main class="relative z-10">
      <HeroSection />
      <SignalsSection />
      <SolutionsSection />
      <HowItWorksSection />
      <WhyICoreSection />
      <RelatedBusinessSection />
      <PlansSection />
      <FinalCtaSection />
    </main>

    <LandingFooter />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import HeroSection from '../components/landing/HeroSection.vue'
import FinalCtaSection from '../components/landing/FinalCtaSection.vue'
import HowItWorksSection from '../components/landing/HowItWorksSection.vue'
import LandingFooter from '../components/landing/LandingFooter.vue'
import LandingNavbar from '../components/landing/LandingNavbar.vue'
import PlansSection from '../components/landing/PlansSection.vue'
import RelatedBusinessSection from '../components/landing/RelatedBusinessSection.vue'
import SignalsSection from '../components/landing/SignalsSection.vue'
import SolutionsSection from '../components/landing/SolutionsSection.vue'
import WhyICoreSection from '../components/landing/WhyICoreSection.vue'

let observer

onMounted(() => {
  const items = document.querySelectorAll('[data-reveal]')
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible')
          observer?.unobserve(entry.target)
        }
      }
    },
    { threshold: 0.16, rootMargin: '0px 0px -8% 0px' },
  )

  items.forEach((item, index) => {
    item.style.setProperty('--reveal-delay', `${Math.min(index * 70, 280)}ms`)
    observer.observe(item)
  })
})

onUnmounted(() => {
  observer?.disconnect()
})
</script>
