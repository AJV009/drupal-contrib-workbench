---
name: drupal-dev-patterns
description: >
  Hook implementations, service/DI patterns, and security patterns for
  Drupal 10/11. Use when implementing hooks, form alters, event subscribers,
  creating services, working with dependency injection, or reviewing code
  for security issues.
---

# Drupal Development Patterns

**Announce at start:** "I'm using the drupal-dev-patterns skill for [hooks/DI/security] guidance."

> **IRON LAW:** NO `\Drupal::` STATIC CALLS IN SERVICE CLASSES. Use constructor injection.

This skill covers three domains. Load only the reference you need:

## Hook Patterns
OOP hooks with `#[Hook]` attribute (Drupal 11+), legacy bridges, form alters,
entity hooks, theme hooks, event subscribers, install/update hooks.

**Full reference:** `references/hook-patterns.md`

**Quick decision:**
- Drupal 11+? Use `#[Hook]` attribute in a Hook class
- Need Drupal 10 compat? Add `#[LegacyHook]` bridge in .module
- Business logic? Delegate to an injectable service, not the hook class

## Service & Dependency Injection
Service definitions, constructor property promotion, interface design,
plugin DI, common Drupal services table, service name discovery.

**Full reference:** `references/service-di-patterns.md`

**Quick decision:**
- Creating a service? Define in `*.services.yml`, use autowire where possible
- Injecting into a plugin? Implement `ContainerFactoryPluginInterface`
- Finding a service name? Read the module's `*.services.yml` directly

## Security Patterns
SQL injection prevention, XSS protection, access control (route + entity),
CSRF protection, file upload validation, security checklist.

**Full reference:** `references/security-patterns.md`

**Quick decision:**
- Database query? Use Entity API (best) or parameterized queries
- User output? Twig auto-escapes. For PHP: `Html::escape()` or `Xss::filter()`
- Route access? Stack `_permission`, `_entity_access`, custom checkers in routing.yml
