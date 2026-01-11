/**
 * addToCart - 商品をカートに追加
 * Generated from TRIR Spec
 */

import {
  CartItem,
  RepositoryContext,
  generateId,
  InvalidQuantityError,
  OutOfStockError,
  ProductNotFoundError,
} from './types';

interface AddToCartInput {
  cartId: string;
  productId: string;
  quantity: number;
}

interface AddToCartOutput {
  cartItem: CartItem;
}

/**
 * カートに商品を追加する
 *
 * @pre quantity > 0
 * @post CartItem が作成される
 * @post Product.stock が quantity 分減少する
 */
export async function addToCart(
  input: AddToCartInput,
  ctx: RepositoryContext
): Promise<AddToCartOutput> {
  const { cartId, productId, quantity } = input;

  // Pre-condition: quantity > 0
  if (quantity <= 0) {
    throw new InvalidQuantityError();
  }

  // Get product to check stock and get price
  const product = await ctx.productRepository.get(productId);
  if (!product) {
    throw new ProductNotFoundError();
  }

  // Check stock availability
  if (product.stock < quantity) {
    throw new OutOfStockError();
  }

  // Post-action 1: Create CartItem
  const cartItem = await ctx.cartItemRepository.create({
    id: generateId(),
    cartId: cartId,
    productId: productId,
    quantity: quantity,
    unitPrice: product.price,
  });

  // Post-action 2: Decrement product stock
  await ctx.productRepository.update(productId, {
    stock: product.stock - quantity,
  });

  return { cartItem };
}
