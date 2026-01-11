/**
 * addToCart Tests
 *
 * Based on TRIR Scenario: add_item_to_cart
 *
 * Given:
 *   - Product: id=prod-001, name="テスト商品", price=1000, stock=10
 *   - Cart: id=cart-001, userId="user-001", totalAmount=0
 *
 * When:
 *   - addToCart({ cartId: "cart-001", productId: "prod-001", quantity: 2 })
 *
 * Then:
 *   - Product.stock should be 8
 *   - Output cartItem.quantity should be 2
 *   - Output cartItem.unitPrice should be 1000
 */

import { describe, it, expect, beforeEach, jest } from '@jest/globals';
import { addToCart } from './addToCart';
import { Product, Cart, CartItem, InvalidQuantityError, OutOfStockError, ProductNotFoundError } from './types';
import { RepositoryContext } from './repositories';

// === Mock Repository Factory ===
function createMockRepository<T extends { id: string }>() {
  const data = new Map<string, T>();
  return {
    get: jest.fn(async (id: string) => data.get(id) ?? null),
    create: jest.fn(async (entity: T) => { data.set(entity.id, entity); return entity; }),
    update: jest.fn(async (id: string, updates: Partial<T>) => {
      const existing = data.get(id);
      if (!existing) throw new Error(`Entity ${id} not found`);
      const updated = { ...existing, ...updates };
      data.set(id, updated);
      return updated;
    }),
    delete: jest.fn(async (id: string) => { data.delete(id); return true; }),
    findBy: jest.fn(async (query: Partial<T>) => Array.from(data.values()).filter(e =>
      Object.entries(query).every(([k, v]) => (e as any)[k] === v)
    )),
    _setData: (entities: T[]) => { data.clear(); entities.forEach(e => data.set(e.id, e)); },
  };
}

describe('addToCart', () => {
  let ctx: RepositoryContext;
  let productsRepo: ReturnType<typeof createMockRepository<Product>>;
  let cartItemsRepo: ReturnType<typeof createMockRepository<CartItem>> & { findByCartId: jest.Mock };

  beforeEach(() => {
    productsRepo = createMockRepository<Product>();
    const cartItemsBase = createMockRepository<CartItem>();
    cartItemsRepo = {
      ...cartItemsBase,
      findByCartId: jest.fn(async (cartId: string) =>
        Array.from((cartItemsBase as any)._data?.values() ?? []).filter((i: CartItem) => i.cartId === cartId)
      ),
    };

    ctx = {
      products: productsRepo,
      carts: createMockRepository<Cart>(),
      cartItems: cartItemsRepo,
      orders: createMockRepository() as any,
      orderItems: createMockRepository() as any,
    };
  });

  describe('Scenario: add_item_to_cart', () => {
    beforeEach(() => {
      // Given: Product prod-001 with stock=10
      productsRepo._setData([{
        id: 'prod-001',
        name: 'テスト商品',
        price: 1000,
        stock: 10,
      }]);

      // Given: Cart cart-001
      (ctx.carts as any)._setData([{
        id: 'cart-001',
        userId: 'user-001',
        totalAmount: 0,
      }]);
    });

    it('should create CartItem with correct quantity and unitPrice', async () => {
      // When
      const result = await addToCart({
        cartId: 'cart-001',
        productId: 'prod-001',
        quantity: 2,
      }, ctx);

      // Then: cartItem should have quantity=2, unitPrice=1000
      expect(result.cartItem.quantity).toBe(2);
      expect(result.cartItem.unitPrice).toBe(1000);
    });

    it('should decrement Product stock by quantity', async () => {
      // When
      await addToCart({
        cartId: 'cart-001',
        productId: 'prod-001',
        quantity: 2,
      }, ctx);

      // Then: Product stock should be 8
      expect(productsRepo.update).toHaveBeenCalledWith('prod-001', { stock: 8 });
    });
  });

  describe('Pre-condition: quantity > 0', () => {
    beforeEach(() => {
      productsRepo._setData([{
        id: 'prod-001',
        name: 'テスト商品',
        price: 1000,
        stock: 10,
      }]);
    });

    it('should throw InvalidQuantityError when quantity is 0', async () => {
      await expect(addToCart({
        cartId: 'cart-001',
        productId: 'prod-001',
        quantity: 0,
      }, ctx)).rejects.toThrow(InvalidQuantityError);
    });

    it('should throw InvalidQuantityError when quantity is negative', async () => {
      await expect(addToCart({
        cartId: 'cart-001',
        productId: 'prod-001',
        quantity: -1,
      }, ctx)).rejects.toThrow(InvalidQuantityError);
    });
  });

  describe('Error handling', () => {
    it('should throw ProductNotFoundError when product does not exist', async () => {
      await expect(addToCart({
        cartId: 'cart-001',
        productId: 'nonexistent',
        quantity: 1,
      }, ctx)).rejects.toThrow(ProductNotFoundError);
    });

    it('should throw OutOfStockError when stock is insufficient', async () => {
      productsRepo._setData([{
        id: 'prod-001',
        name: 'テスト商品',
        price: 1000,
        stock: 1,
      }]);

      await expect(addToCart({
        cartId: 'cart-001',
        productId: 'prod-001',
        quantity: 5,
      }, ctx)).rejects.toThrow(OutOfStockError);
    });
  });
});
