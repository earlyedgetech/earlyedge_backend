from rest_framework import serializers

from .models import PromoCode


class PromoCodeSerializer(serializers.ModelSerializer):
    total_uses = serializers.IntegerField(read_only=True)

    class Meta:
        model = PromoCode
        fields = [
            'id', 'code', 'description',
            'discount_type', 'discount_value',
            'max_total_uses', 'limit_per_user', 'minimum_purchase',
            'start_date', 'end_date',
            'platform', 'is_active', 'first_time_purchase_only', 'auto_apply_at_checkout',
            'show_in_cart', 'total_uses', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'total_uses', 'created_at', 'updated_at']

    def validate_code(self, value):
        value = value.upper()
        queryset = PromoCode.objects.filter(code=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('A promo code with this code already exists.')
        return value

    def validate(self, attrs):
        discount_type = attrs.get('discount_type', getattr(self.instance, 'discount_type', None))
        discount_value = attrs.get('discount_value', getattr(self.instance, 'discount_value', None))
        if discount_type == PromoCode.DISCOUNT_PERCENTAGE and discount_value is not None and discount_value > 100:
            raise serializers.ValidationError({'discount_value': 'Percentage discount cannot exceed 100.'})

        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({'end_date': 'End date cannot be before start date.'})

        return attrs


class PromoCodePublicSerializer(serializers.ModelSerializer):
    """Safe subset shown to shoppers in the checkout cart — no usage-limit
    or analytics internals."""

    class Meta:
        model = PromoCode
        fields = [
            'code', 'description', 'discount_type', 'discount_value',
            'minimum_purchase', 'platform',
        ]
