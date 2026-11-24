import unittest

from coursekit import failure
from coursekit.plan import Plan


def rc(address, rtype, after):
    name = address.split(".")[-1]
    return {"address": address, "type": rtype, "name": name, "mode": "managed",
            "change": {"actions": ["create"], "after": after, "after_unknown": {}}}


def plan(*changes, region="us-central1"):
    return Plan({"resource_changes": list(changes), "configuration": {},
                 "variables": {"region": {"value": region}}})


class WorkloadMathTest(unittest.TestCase):
    def test_even_spread_loses_ceiling_share(self):
        w = failure.Workload("m", "regional-mig", ["a", "b", "c"], 6, 9)
        self.assertEqual(w.after_losing("a"), 4)
        self.assertEqual(w.after_losing("a", at="max"), 6)
        self.assertEqual(w.after_losing("z"), 6)          # zone not used

    def test_uneven_count_uses_worst_zone(self):
        w = failure.Workload("m", "regional-mig", ["a", "b", "c"], 4, 4)
        self.assertEqual(w.after_losing("a"), 2)          # one zone holds 2 of 4

    def test_single_zone_goes_to_zero(self):
        self.assertEqual(failure.Workload("v", "vm", ["a"], 1, 1).after_losing("a"), 0)

    def test_failover_survives(self):
        self.assertEqual(failure.Workload("s", "sql", [], 1, 1).after_losing("a"), 1)


class PlanAnalysisTest(unittest.TestCase):
    def test_spofs(self):
        p = plan(
            rc("google_compute_instance.vm", "google_compute_instance", {"zone": "us-central1-a"}),
            rc("google_sql_database_instance.zonal", "google_sql_database_instance",
               {"settings": [{"availability_type": "ZONAL"}]}),
            rc("google_sql_database_instance.ha", "google_sql_database_instance",
               {"settings": [{"availability_type": "REGIONAL"}]}),
            rc("google_compute_region_instance_group_manager.mig", "google_compute_region_instance_group_manager",
               {"distribution_policy_zones": ["us-central1-a", "us-central1-b"], "target_size": 2}),
            rc("google_container_cluster.zonal", "google_container_cluster", {"location": "us-central1-c"}),
            rc("google_container_cluster.regional", "google_container_cluster", {"location": "us-central1"}),
        )
        self.assertEqual(sorted(failure.single_points_of_failure(p)), [
            "google_compute_instance.vm", "google_container_cluster.zonal", "google_sql_database_instance.zonal"])
        self.assertEqual(failure.worst_case(p)["google_compute_region_instance_group_manager.mig"][0], 1)
        self.assertEqual(failure.worst_case(p)["google_sql_database_instance.zonal"][1], failure.UNKNOWN_ZONE)

    def test_mig_without_zones_uses_region(self):
        p = plan(rc("google_compute_region_instance_group_manager.m", "google_compute_region_instance_group_manager",
                    {"target_size": 4}), region="europe-west2")
        w = failure.workloads(p)[0]
        self.assertEqual(len(w.zones), 3)
        self.assertEqual(failure.worst_case(p)[w.address][0], 2)


class RegionLossTest(unittest.TestCase):
    def test_bucket_locations(self):
        self.assertEqual(failure.bucket_regions("NAM4"), {"us-central1", "us-east1"})
        self.assertEqual(failure.bucket_regions("US"), {"us-*"})
        self.assertEqual(failure.bucket_regions("US-CENTRAL1"), {"us-central1"})

    def test_lose_region(self):
        p = plan(
            rc("google_storage_bucket.regional", "google_storage_bucket", {"location": "US-CENTRAL1"}),
            rc("google_storage_bucket.dual", "google_storage_bucket", {"location": "NAM4", "rpo": "ASYNC_TURBO"}),
            rc("google_artifact_registry_repository.multi", "google_artifact_registry_repository", {"location": "us"}),
            rc("google_sql_database_instance.nobackup", "google_sql_database_instance",
               {"region": "us-central1", "settings": [{"backup_configuration": [{"enabled": False}]}]}),
        )
        lost = failure.lose_region(p, "us-central1")
        self.assertEqual(lost, {"google_storage_bucket.regional": False, "google_storage_bucket.dual": True,
                                "google_artifact_registry_repository.multi": True,
                                "google_sql_database_instance.nobackup": False})
        rpo = {s.address: s.rpo_minutes for s in failure.data_stores(p)}
        self.assertEqual(rpo["google_storage_bucket.dual"], 15)
        self.assertEqual(rpo["google_storage_bucket.regional"], failure.UNLIMITED)

    def test_sql_with_backups_survives_with_daily_rpo(self):
        p = plan(rc("google_sql_database_instance.db", "google_sql_database_instance",
                    {"region": "us-central1", "settings": [{"backup_configuration": [{"enabled": True}]}]}))
        s = failure.data_stores(p)[0]
        self.assertEqual(s.rpo_minutes, 1440)
        self.assertTrue(failure.lose_region(p, "us-central1")[s.address])


if __name__ == "__main__":
    unittest.main()
