from django.core.management.base import BaseCommand, CommandError

from carbon.models import ActivityCategory
from recommendations.models import Recommendation


class Command(BaseCommand):
    help = "Seed the CarbonIQ recommendation catalog."

    RECOMMENDATIONS = [
        # ---------------------------------------------------------
        # Electricity
        # ---------------------------------------------------------
        {
            "title": "Reduce unnecessary electricity consumption",
            "description": (
                "Switch off lights, appliances, and equipment when they "
                "are not needed to reduce avoidable electricity usage."
            ),
            "category": "Electricity",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 80,
            "applicable_segment": "energy-oriented",
        },
        {
            "title": "Improve household energy efficiency",
            "description": (
                "Prefer energy-efficient appliances and everyday practices "
                "to reduce electricity consumption over time."
            ),
            "category": "Electricity",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 75,
            "applicable_segment": "energy-oriented",
        },
        {
            "title": "Reduce standby electricity usage",
            "description": (
                "Disconnect or switch off devices that remain on standby "
                "when they are not required."
            ),
            "category": "Electricity",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 65,
            "applicable_segment": "energy-oriented",
        },

        # ---------------------------------------------------------
        # Transportation
        # ---------------------------------------------------------
        {
            "title": "Reduce unnecessary private-vehicle trips",
            "description": (
                "Combine errands and avoid avoidable private-vehicle "
                "journeys where practical."
            ),
            "category": "Transportation",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 85,
            "applicable_segment": "transport-oriented",
        },
        {
            "title": "Prefer public or shared transportation",
            "description": (
                "Use public transportation, shared mobility, or carpooling "
                "for suitable journeys when practical."
            ),
            "category": "Transportation",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 80,
            "applicable_segment": "transport-oriented",
        },
        {
            "title": "Combine multiple trips into fewer journeys",
            "description": (
                "Plan errands together so that several separate journeys "
                "can be completed in fewer trips."
            ),
            "category": "Transportation",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 70,
            "applicable_segment": "transport-oriented",
        },

        # ---------------------------------------------------------
        # Petrol
        # ---------------------------------------------------------
        {
            "title": "Reduce petrol consumption",
            "description": (
                "Reduce unnecessary petrol usage by combining journeys "
                "and choosing lower-emission travel options where possible."
            ),
            "category": "Petrol",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 85,
            "applicable_segment": "transport-oriented",
        },
        {
            "title": "Avoid unnecessary engine idling",
            "description": (
                "Avoid leaving petrol-powered vehicles idling when stationary "
                "for extended periods."
            ),
            "category": "Petrol",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 65,
            "applicable_segment": "transport-oriented",
        },

        # ---------------------------------------------------------
        # Diesel
        # ---------------------------------------------------------
        {
            "title": "Reduce diesel consumption",
            "description": (
                "Reduce unnecessary diesel usage by planning journeys "
                "efficiently and considering lower-emission alternatives."
            ),
            "category": "Diesel",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 85,
            "applicable_segment": "transport-oriented",
        },
        {
            "title": "Plan diesel-powered journeys efficiently",
            "description": (
                "Combine trips and avoid unnecessary travel to reduce "
                "diesel consumption."
            ),
            "category": "Diesel",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 70,
            "applicable_segment": "transport-oriented",
        },

        # ---------------------------------------------------------
        # Food
        # ---------------------------------------------------------
        {
            "title": "Choose lower-impact food alternatives",
            "description": (
                "Where practical, include food choices with lower associated "
                "carbon emissions as part of a balanced diet."
            ),
            "category": "Rice & Grain",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 65,
            "applicable_segment": "food-oriented",
        },
        {
            "title": "Reduce food waste",
            "description": (
                "Plan food purchases and portions carefully to reduce "
                "avoidable food waste."
            ),
            "category": "Vegetables",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 70,
            "applicable_segment": "food-oriented",
        },
        {
            "title": "Include lower-impact protein alternatives",
            "description": (
                "Consider lower-impact protein alternatives where suitable "
                "for your dietary preferences and requirements."
            ),
            "category": "Tofu",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 65,
            "applicable_segment": "food-oriented",
        },
        {
            "title": "Prefer seasonal and locally available produce",
            "description": (
                "Where practical, consider seasonal and locally available "
                "food choices to support lower-impact consumption patterns."
            ),
            "category": "Fruit",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 55,
            "applicable_segment": "food-oriented",
        },

        # ---------------------------------------------------------
        # Shopping
        # ---------------------------------------------------------
        {
            "title": "Avoid unnecessary clothing purchases",
            "description": (
                "Consider whether new clothing is necessary before purchasing "
                "and reuse suitable items where possible."
            ),
            "category": "Clothing",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 70,
            "applicable_segment": "shopping-oriented",
        },
        {
            "title": "Choose durable and reusable products",
            "description": (
                "Prefer products designed for longer use and reuse existing "
                "items when practical."
            ),
            "category": "Footwear",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 65,
            "applicable_segment": "shopping-oriented",
        },

        # ---------------------------------------------------------
        # Waste
        # ---------------------------------------------------------
        {
            "title": "Improve waste segregation",
            "description": (
                "Separate waste appropriately to support recycling, recovery, "
                "and responsible waste management."
            ),
            "category": "Waste",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 75,
            "applicable_segment": "waste-oriented",
        },
        {
            "title": "Reduce avoidable waste generation",
            "description": (
                "Prefer reusable options and avoid unnecessary disposable "
                "items where practical."
            ),
            "category": "Waste",
            "action_type": Recommendation.ActionType.SUSTAINABILITY,
            "priority": 70,
            "applicable_segment": "waste-oriented",
        },

        # ---------------------------------------------------------
        # Carbon offsets
        # ---------------------------------------------------------
        {
            "title": "Consider verified carbon-offset projects",
            "description": (
                "For residual emissions that cannot reasonably be reduced, "
                "consider credible carbon-offset projects with transparent "
                "impact information."
            ),
            "category": None,
            "action_type": Recommendation.ActionType.OFFSET,
            "priority": 40,
            "applicable_segment": "",
        },
        {
            "title": "Prefer transparent and credible offset providers",
            "description": (
                "When considering offsets, review project transparency, "
                "methodology, verification, and impact reporting."
            ),
            "category": None,
            "action_type": Recommendation.ActionType.OFFSET,
            "priority": 35,
            "applicable_segment": "",
        },
        {
            "title": "Treat offsets as a complementary action",
            "description": (
                "Prioritize reducing avoidable emissions first and consider "
                "offsetting only for residual emissions."
            ),
            "category": None,
            "action_type": Recommendation.ActionType.OFFSET,
            "priority": 50,
            "applicable_segment": "",
        },
    ]

    def handle(self, *args, **options):
        created_count = 0
        existing_count = 0

        for item in self.RECOMMENDATIONS:
            category = None

            if item["category"] is not None:
                try:
                    category = ActivityCategory.objects.get(
                        name=item["category"],
                        is_active=True,
                    )
                except ActivityCategory.DoesNotExist as exc:
                    raise CommandError(
                        f"Active ActivityCategory '{item['category']}' "
                        "does not exist. Run seed_initial_data first."
                    ) from exc

            recommendation, created = Recommendation.objects.get_or_create(
                title=item["title"],
                action_type=item["action_type"],
                defaults={
                    "description": item["description"],
                    "category": category,
                    "priority": item["priority"],
                    "applicable_segment": item["applicable_segment"],
                    "is_active": True,
                },
            )

            if created:
                created_count += 1
            else:
                existing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Recommendation catalog seeding completed successfully."
            )
        )

        self.stdout.write(
            f"Recommendations created : {created_count}"
        )
        self.stdout.write(
            f"Recommendations existing : {existing_count}"
        )
        self.stdout.write(
            f"Recommendations total    : {len(self.RECOMMENDATIONS)}"
        )