#!/usr/bin/env python3
"""
Phase 5: Unsupervised Clustering & Spectral Analysis

- UMAP + k-Means clustering on timing features
- Check if clusters correlate with secret key bits
- PSD (Power Spectral Density) of per-key time series
- t-SNE visualization (saved as figure)
"""

import json
import os
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_CSV = os.path.join(PROJECT_DIR, "data", "raw_timing_traces_v4_vertical.csv")
OUTPUT_JSON = os.path.join(PROJECT_DIR, "data", "phase5_unsupervised.json")
FIGURES_DIR = os.path.join(PROJECT_DIR, "figures")


def main():
    print("=" * 60)
    print("PHASE 5: Unsupervised Clustering & Spectral Analysis")
    print("=" * 60)

    df = pd.read_csv(DATA_CSV)
    print(f"  Loaded {len(df):,} traces, {df['key_id'].nunique()} keys")

    # Aggregate per-key features
    agg = df.groupby("key_id").agg(
        timing_mean=("timing_cycles", "mean"),
        timing_median=("timing_cycles", "median"),
        timing_std=("timing_cycles", "std"),
        timing_min=("timing_cycles", "min"),
        timing_max=("timing_cycles", "max"),
        timing_iqr=("timing_cycles", lambda x: np.percentile(x, 75) - np.percentile(x, 25)),
        timing_skew=("timing_cycles", "skew"),
        timing_kurt=("timing_cycles", lambda x: x.kurtosis()),
        valid_ct=("valid_ct", "first"),
        message_hw=("message_hw", "first"),
        coeff0_hw=("coeff0_hw", "first"),
        sk_byte0=("sk_byte0", "first"),
    ).reset_index()

    agg["sk_byte0_lsb"] = agg["sk_byte0"] % 2
    agg["sk_byte0_parity"] = agg["sk_byte0"].apply(lambda x: bin(x).count("1") % 2)

    features = ["timing_mean", "timing_median", "timing_std", "timing_min",
                "timing_max", "timing_iqr", "timing_skew", "timing_kurt"]
    X = agg[features].values
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    results = {"experiment": "unsupervised_clustering_spectral"}

    # 1. k-Means Clustering
    print("\n  --- k-Means Clustering ---")
    cluster_results = {}
    for k in [2, 3, 4, 5]:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)

        # Check correlation with secret targets
        ari_lsb = adjusted_rand_score(agg["sk_byte0_lsb"].values, labels)
        nmi_lsb = normalized_mutual_info_score(agg["sk_byte0_lsb"].values, labels)
        ari_parity = adjusted_rand_score(agg["sk_byte0_parity"].values, labels)
        ari_valid = adjusted_rand_score(agg["valid_ct"].values, labels)

        cluster_results[f"k={k}"] = {
            "inertia": float(km.inertia_),
            "ari_sk_byte0_lsb": float(ari_lsb),
            "nmi_sk_byte0_lsb": float(nmi_lsb),
            "ari_sk_byte0_parity": float(ari_parity),
            "ari_valid_ct": float(ari_valid),
        }
        print(f"    k={k}: ARI(lsb)={ari_lsb:.4f}, NMI(lsb)={nmi_lsb:.4f}, "
              f"ARI(valid)={ari_valid:.4f}")
    results["kmeans"] = cluster_results

    # 2. UMAP embedding (if available)
    print("\n  --- Dimensionality Reduction ---")
    try:
        import umap
        reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=15)
        embedding = reducer.fit_transform(X_scaled)
        results["umap"] = {"available": True, "shape": list(embedding.shape)}
        print(f"    UMAP: computed 2D embedding ({embedding.shape})")

        # Check if UMAP dimensions correlate with targets
        for dim in [0, 1]:
            corr_lsb, p_lsb = stats.pointbiserialr(agg["sk_byte0_lsb"].values, embedding[:, dim])
            results[f"umap_dim{dim}_corr_lsb"] = {"r": float(corr_lsb), "p": float(p_lsb)}
            print(f"    UMAP dim{dim} vs lsb: r={corr_lsb:.4f}, p={p_lsb:.4f}")
    except ImportError:
        print("    UMAP not available, using t-SNE instead")
        results["umap"] = {"available": False}

    # t-SNE
    from sklearn.manifold import TSNE
    tsne = TSNE(n_components=2, random_state=42, perplexity=30)
    tsne_emb = tsne.fit_transform(X_scaled)
    print(f"    t-SNE: computed 2D embedding ({tsne_emb.shape})")

    for dim in [0, 1]:
        corr, p = stats.pointbiserialr(agg["sk_byte0_lsb"].values, tsne_emb[:, dim])
        results[f"tsne_dim{dim}_corr_lsb"] = {"r": float(corr), "p": float(p)}
        print(f"    t-SNE dim{dim} vs lsb: r={corr:.4f}, p={p:.4f}")

    # Save t-SNE figure
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        os.makedirs(FIGURES_DIR, exist_ok=True)
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))

        # Color by sk_byte0_lsb
        axes[0].scatter(tsne_emb[:, 0], tsne_emb[:, 1],
                        c=agg["sk_byte0_lsb"].values, cmap="coolwarm",
                        alpha=0.7, s=20)
        axes[0].set_title("t-SNE colored by sk_byte0 LSB")
        axes[0].set_xlabel("t-SNE 1")
        axes[0].set_ylabel("t-SNE 2")

        # Color by valid_ct
        axes[1].scatter(tsne_emb[:, 0], tsne_emb[:, 1],
                        c=agg["valid_ct"].values, cmap="RdYlGn",
                        alpha=0.7, s=20)
        axes[1].set_title("t-SNE colored by valid_ct")
        axes[1].set_xlabel("t-SNE 1")

        # Color by sk_byte0
        sc = axes[2].scatter(tsne_emb[:, 0], tsne_emb[:, 1],
                             c=agg["sk_byte0"].values, cmap="viridis",
                             alpha=0.7, s=20)
        axes[2].set_title("t-SNE colored by sk_byte0")
        axes[2].set_xlabel("t-SNE 1")
        plt.colorbar(sc, ax=axes[2])

        plt.tight_layout()
        fig_path = os.path.join(FIGURES_DIR, "fig6_tsne_clustering.png")
        plt.savefig(fig_path, dpi=150)
        plt.close()
        print(f"\n    Saved t-SNE figure to {fig_path}")
    except Exception as e:
        print(f"    Could not save figure: {e}")

    # 3. PSD Analysis of per-key time series
    print("\n  --- Power Spectral Density Analysis ---")
    # Take first 20 keys, compute PSD of their repeat-level time series
    psd_results = {}
    sample_keys = sorted(df["key_id"].unique())[:20]
    peak_freqs = []
    for kid in sample_keys:
        series = df.loc[df["key_id"] == kid, "timing_cycles"].values
        if len(series) < 64:
            continue
        # Compute PSD
        freqs, psd = np.abs(np.fft.rfftfreq(len(series))), np.abs(np.fft.rfft(series - np.mean(series))) ** 2
        # Find peak frequency (excluding DC)
        if len(psd) > 1:
            peak_idx = np.argmax(psd[1:]) + 1
            peak_freqs.append(float(freqs[peak_idx]))

    if peak_freqs:
        psd_results["n_keys_analyzed"] = len(peak_freqs)
        psd_results["peak_freq_mean"] = float(np.mean(peak_freqs))
        psd_results["peak_freq_std"] = float(np.std(peak_freqs))
        # Check if peak freqs are consistent (could indicate systematic pattern)
        psd_results["peak_freq_cv"] = float(np.std(peak_freqs) / np.mean(peak_freqs))
        print(f"    Peak freq mean: {np.mean(peak_freqs):.4f}, std: {np.std(peak_freqs):.4f}")
        print(f"    CV of peak freqs: {psd_results['peak_freq_cv']:.4f} "
              f"({'consistent' if psd_results['peak_freq_cv'] < 0.3 else 'inconsistent'})")
    results["psd_analysis"] = psd_results

    # 4. Correlation matrix of all features with secret targets
    print("\n  --- Feature-Target Correlations ---")
    corr_results = {}
    for feat in features:
        for target in ["sk_byte0_lsb", "sk_byte0_parity", "sk_byte0"]:
            if target in ["sk_byte0_lsb", "sk_byte0_parity"]:
                r, p = stats.pointbiserialr(agg[target].values, agg[feat].values)
            else:
                r, p = stats.pearsonr(agg[target].values, agg[feat].values)
            corr_results[f"{feat}_vs_{target}"] = {"r": float(r), "p": float(p)}
    results["feature_correlations"] = corr_results

    # Print significant ones
    sig_corrs = {k: v for k, v in corr_results.items() if v["p"] < 0.05}
    if sig_corrs:
        print(f"    Significant correlations (p<0.05): {len(sig_corrs)}")
        for k, v in sorted(sig_corrs.items(), key=lambda x: x[1]["p"]):
            print(f"      {k}: r={v['r']:.4f}, p={v['p']:.4e}")
    else:
        print(f"    No significant correlations (p<0.05)")

    # Save
    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
