---
name: rebase-feature-branch
description: Bring the latest main-branch commits into a local feature branch with git rebase instead of merge, keeping history linear, and resolve conflicts commit by commit. Use when the user wants to update a feature branch from main, avoid merge commits, clean up history before a pull request, or is stuck mid-rebase with conflicts.
---

# Rebase a feature branch onto main

Replays the feature branch's commits on top of the latest `main`, so the branch gets main's changes without a merge commit and later merges fast-forward into a linear history ([02:11](https://youtu.be/DkWDHzmMvyg?t=131)). Use it when a clean, linear history matters to the team. If the team doesn't care about merge commits, plain `git merge main` is fine and safer ([01:30](https://youtu.be/DkWDHzmMvyg?t=90)).

## Before you start

- The feature branch must **not** have been pushed or shared. Rebasing rewrites commit hashes, so a pushed branch no longer matches the remote and teammates who pulled it can lose work ([03:23](https://youtu.be/DkWDHzmMvyg?t=203)).
- Check: run `git branch -a`. If the feature branch appears under `remotes/`, stop and use `git merge main` instead, unless the user confirms they know what they're doing ([03:23](https://youtu.be/DkWDHzmMvyg?t=203)).
- Make sure the working tree is clean (`git status`) and local `main` is up to date: `git fetch` and update `main` first *(not in video)*.

## Steps

1. Switch to the feature branch: `git switch <feature-branch>` ([02:11](https://youtu.be/DkWDHzmMvyg?t=131)).
2. Run `git rebase main`. Git sets the feature commits aside and reapplies them one by one on top of the newest `main` commit ([02:11](https://youtu.be/DkWDHzmMvyg?t=131)).
3. If git pauses with a conflict, run `git status` to see which commit is being applied and how many are left ([05:29](https://youtu.be/DkWDHzmMvyg?t=329)).
4. Open each conflicted file, remove the conflict markers and keep the code that should stay ([05:29](https://youtu.be/DkWDHzmMvyg?t=329)).
5. Stage the fixed files: `git add <file>` for every conflicted file ([05:29](https://youtu.be/DkWDHzmMvyg?t=329)).
6. Run `git rebase --continue`. **Don't run `git commit`**: that's the step that differs from a merge ([05:29](https://youtu.be/DkWDHzmMvyg?t=329)).
7. Git opens an editor for the commit message. To keep it unchanged in Vim, press `Esc`, type `:wq` and press Enter ([07:00](https://youtu.be/DkWDHzmMvyg?t=420)). To avoid the editor entirely, use `GIT_EDITOR=true git rebase --continue` *(not in video)*.
8. Repeat steps 3–7 for each commit that conflicts. Each feature commit is reapplied separately, so expect several rounds ([04:37](https://youtu.be/DkWDHzmMvyg?t=277), [07:00](https://youtu.be/DkWDHzmMvyg?t=420)).
9. To give up at any point and return to the state before the rebase: `git rebase --abort` ([04:37](https://youtu.be/DkWDHzmMvyg?t=277)).

## Check your work

- `git status` no longer says a rebase is in progress ([07:00](https://youtu.be/DkWDHzmMvyg?t=420)).
- `git log --oneline --graph` shows the feature commits sitting on top of the latest `main` commit, with no merge commit *(not in video)*.
- The project still builds and its tests pass after the conflict fixes *(not in video)*.

## Pitfalls

- **Rebasing pushed commits.** The golden rule: never rebase commits already pushed, unless you really know what you're doing ([03:23](https://youtu.be/DkWDHzmMvyg?t=203)).
- **Committing during a rebase.** Use `git rebase --continue`, not `git commit` ([05:29](https://youtu.be/DkWDHzmMvyg?t=329)).
- **Waiting too long.** Conflicts grow the longer the branch drifts from main; update often ([00:00](https://youtu.be/DkWDHzmMvyg?t=0)).
- **Getting stuck in Vim.** `Esc`, then `:wq` ([07:00](https://youtu.be/DkWDHzmMvyg?t=420)).

## Source

- Video: "git rebase - Why, When & How to fix conflicts" by Philomatics, https://youtu.be/DkWDHzmMvyg
- Published 2024-06-10. Tools shown: git command line, GitHub pull requests. Core git commands are stable, so this skill is unlikely to go stale.
- Covered but not turned into steps: interactive rebase (`git rebase -i`) for squashing or reordering ([08:15](https://youtu.be/DkWDHzmMvyg?t=495)), and squash-on-merge as an alternative ([01:54](https://youtu.be/DkWDHzmMvyg?t=114)).
