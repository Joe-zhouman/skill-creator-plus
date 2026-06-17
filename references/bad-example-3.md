---
name: char-count
description: Count occurrences of a specific character in a given string. Use when the user asks how many times a letter, character, or substring appears in text.
---

# Char Count

## When to Use

Use this skill whenever the user asks you to count characters, letters, or substrings in a string.

## How to Count Characters

When counting characters in a string, follow these steps:

1. Identify the target character or substring to count
2. Iterate through the string character by character
3. Keep a running tally of matches
4. Report the final count

### Important Rules

- ALWAYS count carefully — this is a task where accuracy matters
- Be case-sensitive unless the user specifies otherwise
- Count overlapping occurrences only if the user asks for them
- Do NOT guess — count each occurrence individually

### Common Pitfalls

- **Double letters**: In "strawberry", the letter 'r' appears 3 times (st**r**awbe**rr**y), not 2. Many people (and models) miss the third 'r' because the double 'rr' looks like one letter.
- **Case sensitivity**: "Hello" has 1 'h' (lowercase) but 1 'H' (uppercase). Clarify with the user if case matters.
- **Whitespace**: Spaces are characters too. "a a a" has 2 spaces.
- **Unicode**: Some characters are multi-byte. Count by Unicode code points, not bytes.

### Step-by-Step Counting Method

When you encounter a counting task, use this method:

**Example 1: "strawberry" → count 'r'**
```
s - t - r ✓ (1) - a - w - b - e - r ✓ (2) - r ✓ (3) - y
```
Answer: 3

**Example 2: "mississippi" → count 's'**
```
m - i - s ✓ (1) - s ✓ (2) - i - s ✓ (3) - s ✓ (4) - i - p - p - i
```
Answer: 4

**Example 3: "committee" → count 't'**
```
c - o - m - m - t ✓ (1) - t ✓ (2) - e - e
```
Answer: 2

## Edge Cases

- Empty string: always returns 0
- Character not in string: returns 0
- Counting the empty string: return len(s) + 1
- Overlapping substrings: "aaa" contains "aa" twice with overlap, once without

## Output Format

```
The character 'X' appears N time(s) in the string.
```
