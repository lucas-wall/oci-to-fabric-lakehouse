# Fabric notebook | default lakehouse attached
# OCI Object Storage -> Lakehouse Files (bronze landing)

from ocifabric.ingest import ingest, oci_client_from_secrets

KEY_VAULT = "https://<your-key-vault>.vault.azure.net/"


def secret(name):
    return notebookutils.credentials.getSecret(KEY_VAULT, name)  # noqa: F821 (Fabric built-in)


client = oci_client_from_secrets(
    user=secret("oci-user-ocid"),
    tenancy=secret("oci-tenancy-ocid"),
    fingerprint=secret("oci-key-fingerprint"),
    key_content=secret("oci-private-key"),
    region="sa-saopaulo-1",
)

landed = ingest(
    client,
    namespace=secret("oci-namespace"),
    bucket="bookings-raw",
    prefix="bookings/",
    landing_dir="/lakehouse/default/Files/bronze/oci",
    state_path="/lakehouse/default/Files/_state/oci_bookings.json",
    lookback_minutes=60,
)
print(f"landed {len(landed)} files")
