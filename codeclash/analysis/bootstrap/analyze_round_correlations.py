#!/usr/bin/env python3

import collections
import json

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize
from scipy.special import logit

from codeclash import REPO_DIR

data = json.loads((REPO_DIR / "round_scores.json").read_text())
onlyrows = collections.defaultdict(list)
for game in data.keys():
    for model_results in data[game]:
        for model in model_results.keys():
            if len(model_results[model]) != 15:
                # print("skipping", game, len(model_results[model]))
                continue
            onlyrows[game].append(model_results[model])


onlyrows = {game: np.array(onlyrows[game]) for game in onlyrows.keys()}
onlyrows["BattleSnake"].shape
plt.hist(onlyrows["BattleSnake"][:, 14])


METHOD = "ar1"
# METHOD = "arp_geometric_decay"
# METHOD = "ar_p"
# METHOD = "same_as_previous"


def ar_residuals_logit(scores: np.ndarray, gammas: np.ndarray, mus: np.ndarray) -> np.ndarray:
    """
    One-step-ahead residuals for AR(p) on logit(scores) with stationary means.

    scores: (T, R) in (0,1)
    gammas: (p,)
    mus: (T,)
    Returns: residuals (T, R) with NaN for the first p columns.
    """
    eps = 1e-6
    Z = logit(np.clip(scores, eps, 1 - eps))
    gammas = np.atleast_1d(gammas).astype(float)
    p = len(gammas)
    T, R = Z.shape
    res = np.full((T, R), np.nan, dtype=float)
    mu = mus[:, None]
    for t in range(p, R):
        hat = mu.copy()
        for k in range(1, p + 1):
            hat += gammas[k - 1] * (Z[:, t - k : t - k + 1] - mu)
        res[:, t] = (Z[:, t : t + 1] - hat).ravel()
    return res


def fit(scores: np.ndarray, p: int = 1):
    """
    Fit AR(p) on logit(scores) by conditional Gaussian MLE (CSS).

    scores: (T, R)
    p: AR order (default 1)
    Returns: (gammas_hat: (p,), mus_hat: (T,), residual_std: float, result)
    """
    T, R = scores.shape
    if R <= p:
        raise ValueError("Number of rounds must exceed p.")

    eps = 1e-6
    Z = logit(np.clip(scores, eps, 1 - eps))

    mu0 = Z.mean(axis=1)  # (T,)
    game0 = np.full(p, 0.3, dtype=float)

    def pack(game: np.ndarray, mu: np.ndarray) -> np.ndarray:
        return np.concatenate([game, mu])

    def unpack(theta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        game = theta[:p]
        mu = theta[p:]
        return game, mu

    valid_mask = np.ones((T, R), dtype=bool)
    valid_mask[:, :p] = False
    N = valid_mask.sum()

    def nll(theta: np.ndarray) -> float:
        game, mu = unpack(theta)
        res = ar_residuals_logit(scores, game, mu)
        e = res[valid_mask]
        sigma2 = (e @ e) / N
        return 0.5 * N * np.log(sigma2)

    theta0 = pack(game0, mu0)
    lower_game = np.full(p, -0.999)
    upper_game = np.full(p, 0.999)
    mu_bounds = [(-np.inf, np.inf)] * T
    bounds = list(zip(lower_game, upper_game)) + mu_bounds

    result = minimize(nll, theta0, method="L-BFGS-B", bounds=bounds)
    game_hat, mu_hat = unpack(result.x)
    res_hat = ar_residuals_logit(scores, game_hat, mu_hat)
    residual_std = np.nanstd(res_hat)

    return game_hat, mu_hat, residual_std, result


def residuals_same_as_previous(scores: np.ndarray):
    """
    Compute residuals for a model where each tournament is predicted using
    the logit of the previous round's score.

    scores: shape (num_tournaments, num_rounds), entries in (0,1)
    Returns: residuals array of shape (num_tournaments, num_rounds)
    """
    eps = 1e-6
    Z = logit(np.clip(scores, eps, 1 - eps))

    num_tournaments, num_rounds = Z.shape
    residuals = np.zeros_like(Z)
    residuals[:, 0] = 0
    residuals[:, 1:] = Z[:, 1:] - Z[:, :-1]
    return residuals


def residuals_same_as_first(scores: np.ndarray):
    """
    Compute residuals for a model where each tournament is predicted using
    the logit of the first round's score.

    scores: shape (num_tournaments, num_rounds), entries in (0,1)
    Returns: residuals array of shape (num_tournaments, num_rounds)
    """
    eps = 1e-6
    Z = logit(np.clip(scores, eps, 1 - eps))
    return Z - Z[:, [0]]


def residuals_all_5050(scores: np.ndarray):
    """
    Compute residuals for a model where each tournament is predicted to be 50% 50%
    """
    num_tournaments, num_rounds = scores.shape
    eps = 1e-6
    Z = logit(np.clip(scores, eps, 1 - eps))
    return Z - logit(0.5)


def residuals_all_mean(scores: np.ndarray):
    """
    Compute residuals for a model where each tournament is predicted to be the mean of the scores
    """
    eps = 1e-6
    Z = logit(np.clip(scores, eps, 1 - eps))
    mean_logits = Z.mean(axis=1, keepdims=True)
    return Z - mean_logits


print("=== baselines ===")
print("same_as_previous")
print(residuals_same_as_previous(onlyrows["BattleSnake"]).std())
print("same_as_first")
print(residuals_same_as_first(onlyrows["BattleSnake"]).std())
print("all_5050")
print(residuals_all_5050(onlyrows["BattleSnake"]).std())
print("all_mean")
print(residuals_all_mean(onlyrows["BattleSnake"]).std())

print("=== fitted ===")

print("p=1")
game_hat, mu_hat, residual_std, result = fit(onlyrows["BattleSnake"], p=1)
print(game_hat, residual_std)

print("p=2")
game_hat, mu_hat, residual_std, result = fit(onlyrows["BattleSnake"], p=2)
print(game_hat, residual_std)

print("p=3")
game_hat, mu_hat, residual_std, result = fit(onlyrows["BattleSnake"], p=3)
print(game_hat, residual_std)
